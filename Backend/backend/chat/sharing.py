"""Shared answers: a public, read-only, 7-day link to one answer."""

import re
import secrets
from datetime import timedelta

from common.audit import audit
from django.db import transaction
from django.utils import timezone

from chat.models import SHARE_DAYS, Message, SharedAnswer
from chat.serializers import shown_sources

TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{32}$')


class NotShareable(Exception):
    pass


def _sources(message):
    """The sources as students saw them; only public links are kept."""
    return [
        {
            'position': source.position,
            'title': source.title,
            'url': source.url if source.url.startswith('https://') else '',
            'heading_path': source.heading_path,
            'page_start': source.page_start,
            'page_end': source.page_end,
            'cited': source.cited,
        }
        for source in shown_sources(message, message.sources.order_by('position'))
    ]


def active_share(message, user, now=None):
    now = now or timezone.now()
    return (
        SharedAnswer.objects.filter(message=message, user=user, revoked_at__isnull=True,
                                    expires_at__gt=now)
        .order_by('-created_at').first()
    )


@transaction.atomic
def share(message, user, *, request_id=None):
    """The answer's active link for this student, created if there is none."""
    if (message.role != Message.Role.ASSISTANT or message.status != Message.Status.COMPLETE
            or not message.content.strip()):
        raise NotShareable('Only finished answers can be shared.')
    existing = active_share(message, user)
    if existing:
        return existing, False
    question = message.parent.content if message.parent_id else ''
    shared = SharedAnswer.objects.create(
        token=secrets.token_urlsafe(24), user=user, message=message, question=question,
        answer=message.content, sources=_sources(message),
        expires_at=timezone.now() + timedelta(days=SHARE_DAYS),
    )
    audit(user, 'share.created', 'message', message.pk, request_id=request_id,
          expires_at=shared.expires_at.isoformat())
    return shared, True


@transaction.atomic
def revoke(message, user, *, request_id=None):
    now = timezone.now()
    revoked = SharedAnswer.objects.filter(
        message=message, user=user, revoked_at__isnull=True, expires_at__gt=now
    ).update(revoked_at=now)
    if revoked:
        audit(user, 'share.revoked', 'message', message.pk, request_id=request_id)
    return revoked


def public(token, now=None):
    """The active share for `token`, or None (unknown, expired and revoked look the same)."""
    if not TOKEN_RE.match(token or ''):
        return None
    shared = SharedAnswer.objects.filter(token=token).first()
    return shared if shared and shared.is_active(now) else None


def purge(now=None, *, days=30, dry_run=False):
    """Links 30 days past their expiry or revocation. Called by `purge_data`."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=days)
    old = SharedAnswer.objects.filter(expires_at__lt=cutoff) | SharedAnswer.objects.filter(
        revoked_at__lt=cutoff
    )
    count = old.count()
    if count and not dry_run:
        old.delete()
    return count
