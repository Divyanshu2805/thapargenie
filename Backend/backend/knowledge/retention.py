"""Knowledge base retention. Called by `manage.py purge_data`."""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from knowledge.models import Document, DocumentStatus
from knowledge.storage import StorageError, get_storage

logger = logging.getLogger(__name__)

STORAGE_PREFIX = 'documents'
# A file uploaded moments ago may not have its row committed yet; leave young files alone.
ORPHAN_GRACE = timedelta(days=1)


def purge_failed_documents(now=None, *, dry_run=False):
    """Documents that failed processing and were left alone for the retention period."""
    now = now or timezone.now()
    stale = Document.objects.filter(
        status=DocumentStatus.FAILED,
        updated_at__lt=now - timedelta(days=settings.RETENTION_FAILED_DOCUMENT_DAYS),
    )
    paths = [path for path in stale.values_list('storage_path', flat=True) if path]
    count = stale.count()
    if dry_run or not count:
        return count
    stale.delete()
    try:
        get_storage().delete(paths)
    except StorageError:
        # The rows are gone; the files are private and the orphan sweep retries them.
        logger.warning('Could not delete %d stored files of purged documents.', len(paths))
    return count


def _parse(timestamp):
    try:
        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None


def purge_orphaned_files(now=None, *, dry_run=False):
    """Stored originals whose document row no longer exists (e.g. a delete whose file
    removal failed). Returns the number of files removed."""
    now = now or timezone.now()
    storage = get_storage()
    stored = storage.list(STORAGE_PREFIX)
    known = set(Document.objects.exclude(storage_path='').values_list('storage_path', flat=True))
    orphans = []
    for path, created in stored.items():
        created_at = _parse(created)
        if path not in known and created_at is not None and created_at < now - ORPHAN_GRACE:
            orphans.append(path)
    if orphans and not dry_run:
        storage.delete(orphans)
    return len(orphans)
