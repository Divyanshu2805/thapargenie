"""Knowledge base operations. Views call these; nothing else writes documents."""

import hashlib
import logging

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from common.safe_http import validate_url
from django.conf import settings
from django.db import transaction

from knowledge import jobs
from knowledge.ingest.extract import open_pdf
from knowledge.ingest.filetypes import EXTENSIONS, MIME_TYPES, UnsupportedFile, detect
from knowledge.models import Chunk, Document, DocumentStatus, SourceType
from knowledge.signals import knowledge_changed
from knowledge.storage import get_storage

EDITABLE_FIELDS = (
    'title',
    'category',
    'department',
    'academic_year',
    'effective_date',
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
