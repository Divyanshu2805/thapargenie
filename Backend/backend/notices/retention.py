"""Notice retention. Called by `manage.py purge_data`."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from notices.models import Notice


def purge(now=None, *, dry_run=False):
    """Delete notices that expired more than the retention period ago; never-expiring ones stay.

    Their knowledge-base copies are kept (not current) and follow the documents' own rules.
    """
    now = now or timezone.now()
    old = Notice.objects.filter(
        expires_at__lt=now - timedelta(days=settings.RETENTION_NOTICE_DAYS)
    )
    count = old.count()
    if count and not dry_run:
        old.delete()
    return count
