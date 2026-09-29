"""Small fire-and-forget jobs after an answer (titles, memory). Failures only get logged.

These are nice-to-have, so the queue is bounded: under heavy load extra jobs are dropped
(a summary is retried after the next answer) instead of piling up, because a process that
is restarting has to wait for whatever is still queued. `shutdown()` discards the queue.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections, connections

logger = logging.getLogger(__name__)

# Jobs waiting or running at once; more than this are dropped.
MAX_QUEUED = 50

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='chat-bg')
_lock = threading.Lock()
_queued = 0

# Tests set this to True so jobs run inline and can be asserted on.
RUN_INLINE = False


def _wrap(function, *args):
    close_old_connections()
    try:
        function(*args)
    except Exception:
        logger.exception('Background job %s failed', function.__name__)
    finally:
        connections.close_all()


def _claim_slot():
    global _queued
    with _lock:
        if _queued >= MAX_QUEUED:
            return False
        _queued += 1
        return True


def _release_slot(_future=None):
    global _queued
    with _lock:
        _queued -= 1


def submit(function, *args):
    if RUN_INLINE:
        try:
            function(*args)
        except Exception:
            logger.exception('Background job %s failed', function.__name__)
        return
    if not _claim_slot():
        logger.warning('Background queue is full (%d jobs); dropped %s', MAX_QUEUED,
                       function.__name__)
        return
    try:
        future = _executor.submit(_wrap, function, *args)
    except RuntimeError:
        # The worker is shutting down; these jobs are optional.
        _release_slot()
        logger.info('Worker is shutting down; skipped %s', function.__name__)
        return
    # Also runs when the job is cancelled by shutdown(), so the count stays right.
    future.add_done_callback(_release_slot)


def shutdown():
    """Drop jobs that have not started, so a restarting worker only waits for running ones."""
    _executor.shutdown(wait=False, cancel_futures=True)
