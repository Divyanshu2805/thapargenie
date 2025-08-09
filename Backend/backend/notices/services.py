"""Notices. Views call these; nothing else writes notices.

An answerable notice keeps a text document in the knowledge base while it is published
(and after it expires, marked not current). Drafts and scheduled notices have none:
`is_current` only ranks documents, it does not hide them from search. The 5-minute
sweep (`sync_due_documents`) catches notices whose schedule or expiry passed since.
"""

import logging
from datetime import timedelta

from common.audit import audit
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from knowledge import services as knowledge
from knowledge.models import Category, Document, DocumentStatus

from notices.models import Notice

logger = logging.getLogger(__name__)

EDITABLE_FIELDS = (
    'title', 'body', 'category', 'importance', 'is_pinned', 'is_draft', 'publish_at',
    'expires_at', 'link_url', 'answerable',
)
MAX_OFFICIAL_DAYS = 90
OFFICIAL_LIMIT = 30
STUDENT_LIMIT = 100


# -- student side ---------------------------------------------------------------------

def student_notices(*, category=None, now=None):
    notices = Notice.objects.visible(now).order_by('-is_pinned', '-publish_at', '-id')
    if category:
        notices = notices.filter(category=category)
    return notices[:STUDENT_LIMIT]


def official_documents(days=30, now=None):
    """Knowledge documents filed under Notices that finished processing recently.

    Copies of posted notices are left out; they are already on the page.
    """
    now = now or timezone.now()
    return (
        Document.objects.filter(
            category=Category.NOTICES, status=DocumentStatus.READY, is_current=True,
            processed_at__gte=now - timedelta(days=days), notices__isnull=True,
        )
        .order_by('-processed_at')
    )


def app_config_fields(now=None):
    """`latest_notice_at` and `important_notice` for `GET /app-config`."""
    now = now or timezone.now()
    visible = Notice.objects.visible(now)
    latest = visible.aggregate(latest=Max('publish_at'))['latest']
    official = official_documents(MAX_OFFICIAL_DAYS, now).aggregate(
        latest=Max('processed_at'))['latest']
    important = (
        visible.filter(importance=Notice.Importance.IMPORTANT)
        .order_by('-is_pinned', '-publish_at').values('id', 'title').first()
    )
    return {
        'latest_notice_at': max(filter(None, (latest, official)), default=None),
        'important_notice': (
            {'id': str(important['id']), 'title': important['title']} if important else None
        ),
    }


# -- admin side -----------------------------------------------------------------------

def _apply(notice, changes, now):
    creating = notice._state.adding
    was_draft = not creating and notice.is_draft
    for key in EDITABLE_FIELDS:
        if key in changes:
            setattr(notice, key, changes[key])
    if changes.get('publish_at') is None and (creating or 'publish_at' in changes):
        notice.publish_at = now
    # Publishing a draft that was dated in the past posts it now, so it shows as new.
    if was_draft and not notice.is_draft and 'publish_at' not in changes \
            and notice.publish_at < now:
        notice.publish_at = now


@transaction.atomic
def create_notice(data, *, user, request_id=None):
    now = timezone.now()
    notice = Notice(created_by=user, updated_by=user)
    _apply(notice, data, now)
    notice.full_clean(exclude=['document'])
    notice.save()
    audit(user, 'notice.created', 'notice', notice.pk, request_id=request_id,
          state=notice.state(now), answerable=notice.answerable)
    sync_document(notice, user=user, request_id=request_id, now=now)
    return notice


@transaction.atomic
def update_notice(notice, changes, *, user, request_id=None):
    now = timezone.now()
    notice = Notice.objects.select_for_update().get(pk=notice.pk)
    before = {key: getattr(notice, key) for key in EDITABLE_FIELDS}
    _apply(notice, changes, now)
    changed = sorted(key for key in EDITABLE_FIELDS if getattr(notice, key) != before[key])
    if not changed:
        return notice
    notice.updated_by = user
    notice.full_clean(exclude=['document'])
    notice.save()
    audit(user, 'notice.updated', 'notice', notice.pk, request_id=request_id,
          fields=changed, state=notice.state(now))
    sync_document(notice, user=user, request_id=request_id, now=now)
    return notice


@transaction.atomic
def delete_notice(notice, *, delete_document=False, user, request_id=None):
    document = notice.document
    audit(user, 'notice.deleted', 'notice', notice.pk, request_id=request_id,
          title=notice.title, document_deleted=bool(document and delete_document))
    notice.delete()
    if document is None:
        return
    if delete_document:
        knowledge.delete_document(document, user=user, request_id=request_id)
    elif document.is_current:
        knowledge.update_document(document, {'is_current': False}, user=user,
                                  request_id=request_id)


# -- knowledge-base copy --------------------------------------------------------------

def document_text(notice):
    """What the chatbot reads: the notice with its dates and link spelled out."""
    posted = timezone.localtime(notice.publish_at)
    dates = f'Notice posted on {posted:%d %B %Y}.'
    if notice.expires_at:
        dates += f' Valid until {timezone.localtime(notice.expires_at):%d %B %Y}.'
    parts = [f'# {notice.title}', dates, notice.body.strip()]
    if notice.link_url:
        parts.append(f'Official notice: {notice.link_url}')
    return '\n\n'.join(part for part in parts if part)


def _document_meta(notice, expired):
    return {
        'title': notice.title,
        'category': notice.category,
        'effective_date': timezone.localdate(notice.publish_at),
        'valid_until': timezone.localdate(notice.expires_at) if notice.expires_at else None,
        'source_url': notice.link_url,
        'is_current': not expired,
    }


def sync_document(notice, *, user=None, request_id=None, now=None):
    """Bring the notice's knowledge-base copy in line with the notice."""
    now = now or timezone.now()
    state = notice.state(now)
    document = notice.document
    if not notice.answerable or state in (Notice.State.DRAFT, Notice.State.SCHEDULED):
        if document is not None:
            notice.document = None
            notice.save(update_fields=['document'])
            knowledge.delete_document(document, user=user, request_id=request_id)
        return
    expired = state == Notice.State.EXPIRED
    meta = _document_meta(notice, expired)
    if document is None:
        if expired:
            return
        title = meta.pop('title')
        notice.document = knowledge.create_from_text(
            title=title, text=document_text(notice), meta={**meta, 'contextualize': False},
            user=user, request_id=request_id,
        )
        notice.save(update_fields=['document'])
        return
    knowledge.update_document(document, meta, user=user, request_id=request_id)
    if not knowledge.replace_text(document, document_text(notice), user=user,
                                  request_id=request_id):
        logger.info('Notice %s: its document is being processed; the sweep will update it',
                    notice.pk)


def _out_of_sync(notice, now):
    state = notice.state(now)
    document = notice.document
    if not notice.answerable or state in (Notice.State.DRAFT, Notice.State.SCHEDULED):
        return document is not None
    if document is None:
        return state == Notice.State.PUBLISHED
    if document.is_current == (state == Notice.State.EXPIRED):
        return True
    if document.status == DocumentStatus.PROCESSING:
        return False
    text = document_text(notice).strip().encode()
    return knowledge._hash(text) != document.content_hash


def sync_due_documents(now=None):
    """Fix copies whose notice was scheduled, expired or edited mid-processing since.

    Runs every 5 minutes in the web process. Returns the number of notices synced.
    """
    now = now or timezone.now()
    candidates = Notice.objects.select_related('document').filter(
        is_draft=False, answerable=True, publish_at__lte=now,
    ) | Notice.objects.select_related('document').filter(document__isnull=False)
    synced = 0
    for notice in candidates.distinct():
        if not _out_of_sync(notice, now):
            continue
        try:
            with transaction.atomic():
                sync_document(notice, now=now)
            synced += 1
        except Exception:
            logger.exception('Could not sync the knowledge-base copy of notice %s', notice.pk)
    if synced:
        logger.info('Synced the knowledge-base copies of %d notices', synced)
    return synced
