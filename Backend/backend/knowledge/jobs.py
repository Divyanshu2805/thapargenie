"""Background document processing inside the web process.

State lives in the database (document.status), so nothing is lost when the process
restarts: `requeue_stale()` puts interrupted work back in the queue, and claiming is
atomic, so running it from several workers is safe.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import close_old_connections, connections, transaction
from django.utils import timezone

from knowledge.models import Document, DocumentStatus

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ingest')


def _run(document_id):
    from knowledge.ingest.pipeline import process_document

    close_old_connections()
    try:
        process_document(document_id)
    except Exception:
        logger.exception('Background processing crashed for %s', document_id)
    finally:
        connections.close_all()


def enqueue(document_id):
    """Process after the current transaction commits (so the worker sees the row)."""
    transaction.on_commit(lambda: _executor.submit(_run, document_id))


def requeue_stale():
    """Re-queue documents left mid-processing by a restart, then queue all waiting ones.

    Safe to run from several processes at once: `claim()` lets only one of them work on
    a document; the others return immediately.
    """
    cutoff = timezone.now() - STALE_AFTER
    stale = Document.objects.filter(status=DocumentStatus.PROCESSING, updated_at__lt=cutoff).update(
        status=DocumentStatus.QUEUED, status_detail='Re-queued after an interruption'
    )
    waiting = list(
        Document.objects.filter(status=DocumentStatus.QUEUED).values_list('pk', flat=True)
    )
    for document_id in waiting:
        _executor.submit(_run, document_id)
    if stale or waiting:
        logger.info('Recovery: %d interrupted documents re-queued, %d queued for processing',
                    stale, len(waiting))
    return len(waiting)


_sweeps = []


def register_sweep(sweep):
    """Also run `sweep()` in the recovery loop; for apps that keep documents in sync."""
    if sweep not in _sweeps:
        _sweeps.append(sweep)
