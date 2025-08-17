"""Chat data retention. Called by `manage.py purge_data`."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat import engine, sharing
from chat.models import AnswerCache, AnswerTrace, Conversation, SiteFeedback, UsageDaily


def _delete(queryset, dry_run):
    if dry_run:
        return queryset.count()
    # `delete()` returns the cascade total; report only the rows this rule targets.
    count = queryset.count()
    queryset.delete()
    return count


def purge(now=None, *, dry_run=False):
    """Apply every chat retention rule. Returns {rule: rows affected}."""
    now = now or timezone.now()
    results = {}
    with transaction.atomic():
        # Inactive conversations go, with their messages, sources, feedback and traces.
        results['conversations'] = _delete(
            Conversation.objects.filter(
                last_message_at__lt=now - timedelta(days=settings.RETENTION_CONVERSATION_DAYS)
            ),
            dry_run,
        )
        results['answer_traces'] = _delete(
            AnswerTrace.objects.filter(
                created_at__lt=now - timedelta(days=settings.RETENTION_TRACE_DAYS)
            ),
            dry_run,
        )
        results['answer_cache'] = _delete(AnswerCache.objects.filter(expires_at__lt=now), dry_run)
        results['usage_days'] = _delete(
            UsageDaily.objects.filter(
                day__lt=(now - timedelta(days=settings.RETENTION_USAGE_DAYS)).date()
            ),
            dry_run,
        )
        results['site_feedback'] = _delete(
            SiteFeedback.objects.filter(
                created_at__lt=now - timedelta(days=settings.RETENTION_SITE_FEEDBACK_DAYS)
            ),
            dry_run,
        )
        results['shared_links'] = sharing.purge(now, dry_run=dry_run)
        if dry_run:
            results['stale_streams'] = engine.stale_streams().count()
        else:
            results['stale_streams'] = engine.expire_stale_streams()
    return results
