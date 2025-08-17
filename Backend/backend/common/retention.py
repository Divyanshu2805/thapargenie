"""Audit log retention. The audit table belongs to the auth app, which
stays unchanged; this only removes events older than the retention period."""

from datetime import timedelta

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from django.conf import settings
from django.utils import timezone


def purge_audit_events(now=None, *, dry_run=False):
    now = now or timezone.now()
    old = AuditEvent.objects.filter(
        created_at__lt=now - timedelta(days=settings.RETENTION_AUDIT_DAYS)
    )
    count = old.count()
    if count and not dry_run:
        old.delete()
    return count


def record_purge(results):
    """One content-free audit event per purge run, so the log shows retention working."""
    return AuditEvent.objects.create(
        actor=None,
        actor_kind=AuditActorKind.SERVICE,
        action='retention.purged',
        resource_type='retention',
        outcome=AuditOutcome.SUCCEEDED,
        metadata={'deleted': results},
    )
