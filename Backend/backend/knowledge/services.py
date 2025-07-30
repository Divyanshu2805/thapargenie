"""Knowledge base operations. Views call these; nothing else writes documents."""

import hashlib
import logging
from datetime import timedelta

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from common.audit import audit
from common.safe_http import validate_url
from common.text import estimate_tokens
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rag.llm import get_llm

from knowledge import jobs
from knowledge.ingest.extract import open_pdf
from knowledge.ingest.filetypes import EXTENSIONS, MIME_TYPES, UnsupportedFile, detect
from knowledge.ingest.pipeline import build_search_text
from knowledge.models import MAX_CHUNK_CHARS, Chunk, Document, DocumentStatus, SourceType
from knowledge.signals import knowledge_changed
from knowledge.storage import get_storage

EDITABLE_FIELDS = (
    'title',
    'category',
    'department',
    'academic_year',
    'effective_date',
    'valid_until',
    'is_current',
    'source_url',
    'contextualize',
)
# Fields that appear in chunk search text: changing them requires re-embedding.
SEARCH_HEADER_FIELDS = {'title', 'category', 'department', 'academic_year'}
# Fields copied onto every chunk for filtering.
CHUNK_FIELDS = ('category', 'department', 'is_current')

logger = logging.getLogger(__name__)


class DuplicateDocument(Exception):
    def __init__(self, existing):
        super().__init__(f'This content already exists as "{existing.title}".')
        self.existing = existing


class InvalidTransition(Exception):
    pass


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _audit(actor, action, document, request_id=None, **metadata):
    AuditEvent.objects.create(
        actor=actor,
        actor_kind=AuditActorKind.USER if actor else AuditActorKind.SERVICE,
        action=action,
        resource_type='document',
        resource_id=str(document.pk),
        outcome=AuditOutcome.SUCCEEDED,
        request_id=request_id,
        metadata=metadata,
    )


def _changed():
    transaction.on_commit(lambda: knowledge_changed.send(sender=Document))


def _check_duplicate(content_hash):
    existing = Document.objects.filter(content_hash=content_hash).first()
    if existing:
        raise DuplicateDocument(existing)


def _is_expired(document):
    return bool(document.valid_until) and document.valid_until < timezone.localdate()


def _new_document(*, source_type, content_hash, meta, user):
    fields = {key: value for key, value in meta.items() if key in EDITABLE_FIELDS + ('parser',)}
    document = Document(
        source_type=source_type,
        content_hash=content_hash,
        status=DocumentStatus.QUEUED,
        created_by=user,
        updated_by=user,
        **fields,
    )
    if _is_expired(document):
        document.is_current = False
    document.full_clean(exclude=['title'] if not fields.get('title') else None)
    return document


def create_from_upload(*, data, filename, meta, user, request_id=None):
    max_bytes = settings.INGEST_MAX_FILE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise UnsupportedFile(f'Files are limited to {settings.INGEST_MAX_FILE_MB} MB.')
    source_type = detect(data, filename)
    page_count = None
    if source_type == SourceType.PDF:
        page_count = len(open_pdf(data).pages)
        if page_count > settings.INGEST_MAX_PAGES:
            raise UnsupportedFile(
                f'The PDF has {page_count} pages; the limit is {settings.INGEST_MAX_PAGES}.'
            )
    content_hash = _hash(data)
    _check_duplicate(content_hash)

    meta = {'title': filename.rsplit('.', 1)[0][:300], **meta}
    document = _new_document(source_type=source_type, content_hash=content_hash, meta=meta,
                             user=user)
    document.original_filename = filename[:255]
    document.mime_type = MIME_TYPES[source_type]
    document.file_size = len(data)
    document.page_count = page_count
    document.storage_path = f'documents/{document.pk}.{EXTENSIONS[source_type]}'
    # Upload first: a failed upload must not leave a row pointing at nothing.
    get_storage().upload(document.storage_path, data, document.mime_type)
    with transaction.atomic():
        document.save()
        _audit(user, 'document.created', document, request_id, source='upload',
               filename=document.original_filename)
        jobs.enqueue(document.pk)
    return document


def create_from_url(*, url, meta, user, request_id=None):
    validate_url(url)
    content_hash = _hash(f'url:{url}'.encode())
    _check_duplicate(content_hash)
    document = _new_document(
        source_type=SourceType.URL,
        content_hash=content_hash,
        meta={**meta, 'source_url': url},
        user=user,
    )
    with transaction.atomic():
        document.save()
        _audit(user, 'document.created', document, request_id, source='url')
        jobs.enqueue(document.pk)
    return document


def create_from_text(*, title, text, meta, user, request_id=None):
    data = text.strip().encode()
    if not data:
        raise UnsupportedFile('The text is empty.')
    content_hash = _hash(data)
    _check_duplicate(content_hash)
    document = _new_document(
        source_type=SourceType.TEXT,
        content_hash=content_hash,
        meta={**meta, 'title': title},
        user=user,
    )
    document.mime_type = MIME_TYPES[SourceType.TEXT]
    document.file_size = len(data)
    document.storage_path = f'documents/{document.pk}.txt'
    get_storage().upload(document.storage_path, data, document.mime_type)
    with transaction.atomic():
        document.save()
        _audit(user, 'document.created', document, request_id, source='text')
        jobs.enqueue(document.pk)
    return document


@transaction.atomic
def update_document(document, changes, *, user, request_id=None):
    changes = {key: value for key, value in changes.items() if key in EDITABLE_FIELDS}
    changed = {key for key, value in changes.items() if getattr(document, key) != value}
    if not changed:
        return document
    for key in changed:
        setattr(document, key, changes[key])
    if _is_expired(document) and document.is_current:
        if changes.get('is_current') is True:
            raise ValidationError({'is_current': ['Extend or clear "Valid until" first.']})
        document.is_current = False
        changed.add('is_current')
    document.updated_by = user
    document.full_clean()
    document.save()
    chunk_updates = {key: getattr(document, key) for key in CHUNK_FIELDS if key in changed}
    if chunk_updates:
        Chunk.objects.filter(document=document).update(**chunk_updates)
    _audit(user, 'document.updated', document, request_id, fields=sorted(changed))
    if changed & SEARCH_HEADER_FIELDS and document.status == DocumentStatus.READY:
        _requeue(document)
    else:
        _changed()
    return document


def _requeue(document):
    Document.objects.filter(pk=document.pk).update(
        status=DocumentStatus.QUEUED, status_detail='Waiting to be processed', error=''
    )
    document.status = DocumentStatus.QUEUED
    jobs.enqueue(document.pk)


@transaction.atomic
def reprocess(document, *, user, parser=None, request_id=None):
    """Re-extract, re-chunk and re-embed. `parser` switches e.g. a scanned PDF to smart."""
    if document.status in (DocumentStatus.QUEUED, DocumentStatus.PROCESSING):
        raise InvalidTransition('The document is already being processed.')
    if parser and parser != document.parser:
        document.parser = parser
        document.updated_by = user
        document.full_clean()
        document.save(update_fields=['parser', 'updated_by', 'updated_at'])
    _requeue(document)
    _audit(user, 'document.reprocessed', document, request_id, parser=document.parser)
    return document


@transaction.atomic
def set_enabled(document, enabled, *, user, request_id=None):
    allowed = DocumentStatus.DISABLED if enabled else DocumentStatus.READY
    if document.status != allowed:
        raise InvalidTransition('Only ready documents can be disabled, and only disabled '
                                'documents can be enabled.')
    document.status = DocumentStatus.READY if enabled else DocumentStatus.DISABLED
    document.updated_by = user
    document.save(update_fields=['status', 'updated_by', 'updated_at'])
    Chunk.objects.filter(document=document).update(is_searchable=enabled)
    _audit(user, 'document.enabled' if enabled else 'document.disabled', document, request_id)
    _changed()
    return document


EXPIRY_WARNING_DAYS = 30
VALIDITY_FILTERS = ('expiring', 'expired')


def validity_filter(name, today=None):
    """A Q for the documents list: `expiring` within the warning window, or `expired`."""
    today = today or timezone.localdate()
    if name == 'expired':
        return Q(valid_until__lt=today)
    return Q(valid_until__gte=today,
             valid_until__lte=today + timedelta(days=EXPIRY_WARNING_DAYS))


def expiry_summary(today=None, limit=5):
    """For the admin Overview: what expires soon, and how many are already past."""
    today = today or timezone.localdate()
    soon = Document.objects.filter(validity_filter('expiring', today)).order_by('valid_until')
    return {
        'expiring_soon': soon.count(),
        'expiring': [
            {'id': str(pk), 'title': title, 'valid_until': valid_until.isoformat()}
            for pk, title, valid_until in soon.values_list('pk', 'title', 'valid_until')[:limit]
        ],
        'expired': Document.objects.filter(validity_filter('expired', today)).count(),
    }


def expire_due_documents(*, today=None, dry_run=False):
    """Mark current documents whose `valid_until` has passed as not current.

    Safe to run from several processes at once: each document is flipped with a
    conditional update, and only the process whose update matched records it.
    Returns the number of documents expired (or due, with `dry_run`).
    """
    today = today or timezone.localdate()
    due = Document.objects.filter(is_current=True, valid_until__lt=today)
    if dry_run:
        return due.count()
    expired = 0
    for document_id, valid_until in due.values_list('pk', 'valid_until'):
        with transaction.atomic():
            flipped = Document.objects.filter(pk=document_id, is_current=True).update(
                is_current=False, updated_at=timezone.now()
            )
            if not flipped:
                continue
            Chunk.objects.filter(document_id=document_id).update(is_current=False)
            AuditEvent.objects.create(
                actor=None,
                actor_kind=AuditActorKind.SERVICE,
                action='document.expired',
                resource_type='document',
                resource_id=str(document_id),
                outcome=AuditOutcome.SUCCEEDED,
                metadata={'valid_until': valid_until.isoformat()},
            )
        expired += 1
    if expired:
        logger.info('Marked %d documents not current: past their "valid until" date', expired)
        knowledge_changed.send(sender=Document)
    return expired


def delete_document(document, *, user, request_id=None):
    path = document.storage_path
    with transaction.atomic():
        _audit(user, 'document.deleted', document, request_id, title=document.title)
        document.delete()
        _changed()
    if path:
        # After commit: if storage fails the row is already gone, so the orphaned file is
        # harmless (private) and is picked up by the retention purge.
        get_storage().delete([path])


def _check_chunk_editable(document):
    if document.status in (DocumentStatus.QUEUED, DocumentStatus.PROCESSING):
        raise InvalidTransition('The document is being processed; edit its chunks afterwards.')


def update_chunk(chunk, changes, *, user, request_id=None):
    """Edit one chunk's text and re-embed just that chunk.

    The contextual sentence (if the document was contextualized) is not stored on its
    own, so an edited chunk's search text is rebuilt without it.
    """
    document = chunk.document
    _check_chunk_editable(document)
    content = changes.get('content', chunk.content).strip()
    heading_path = changes.get('heading_path', chunk.heading_path).strip()[:500]
    if not content:
        raise UnsupportedFile('A chunk cannot be empty.')
    if len(content) > MAX_CHUNK_CHARS:
        raise UnsupportedFile(f'A chunk is limited to {MAX_CHUNK_CHARS} characters.')
    if content == chunk.content and heading_path == chunk.heading_path:
        return chunk

    search_text = build_search_text(document, content, heading_path)
    # The LLM call happens outside the transaction so no row is locked while it runs.
    llm = get_llm()
    vector = llm.embed_documents([search_text], titles=[document.title])[0]
    token_delta = estimate_tokens(content) - chunk.token_count
    with transaction.atomic():
        chunk.content = content
        chunk.heading_path = heading_path
        chunk.search_text = search_text
        chunk.token_count += token_delta
        chunk.embedding = vector
        chunk.embedding_model = llm.embed_model
        chunk.save()
        Document.objects.filter(pk=document.pk).update(
            token_count=F('token_count') + token_delta, updated_by=user
        )
        audit(user, 'chunk.updated', 'chunk', chunk.pk, request_id=request_id,
              document_id=str(document.pk), chunk_index=chunk.chunk_index)
        _changed()
    return chunk


def delete_chunk(chunk, *, user, request_id=None):
    document = chunk.document
    _check_chunk_editable(document)
    with transaction.atomic():
        audit(user, 'chunk.deleted', 'chunk', chunk.pk, request_id=request_id,
              document_id=str(document.pk), chunk_index=chunk.chunk_index)
        Document.objects.filter(pk=document.pk).update(
            chunk_count=F('chunk_count') - 1,
            token_count=F('token_count') - chunk.token_count,
            updated_by=user,
        )
        chunk.delete()
        _changed()
