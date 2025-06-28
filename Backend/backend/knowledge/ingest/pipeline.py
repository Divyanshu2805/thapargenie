"""Document processing: source bytes -> Markdown -> chunks -> embeddings -> searchable.

Each document is claimed atomically (queued -> processing), so the same document is
never processed twice even if two workers pick it up. Chunks are swapped in a single
transaction: a reprocessed document stays searchable on its old chunks until the new
ones are ready.
"""

import logging

from common.safe_http import FetchError, UnsafeURLError, fetch
from common.text import truncate
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rag.aliases import expand
from rag.llm import LLMError, QuotaExhausted, get_llm

from knowledge.ingest.chunk import ChunkDraft, build_chunks, search_header
from knowledge.ingest.extract import extract
from knowledge.ingest.filetypes import UnsupportedFile
from knowledge.models import Category, Chunk, Document, DocumentStatus, SourceType
from knowledge.signals import knowledge_changed
from knowledge.storage import StorageError, get_storage

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """A failure with a message that is safe to show to admins."""


def progress(document, detail):
    Document.objects.filter(pk=document.pk).update(
        status_detail=detail[:200], updated_at=timezone.now()
    )


def claim(document_id):
    """queued -> processing, atomically. Returns the document, or None if not claimable."""
    updated = Document.objects.filter(pk=document_id, status=DocumentStatus.QUEUED).update(
        status=DocumentStatus.PROCESSING,
        status_detail='Starting',
        error='',
        updated_at=timezone.now(),
    )
    return Document.objects.get(pk=document_id) if updated else None


def build_search_text(document, content, heading_path=''):
    header = search_header(
        title=document.title,
        category_label=Category(document.category).label,
        department=document.department,
        heading_path=heading_path,
        academic_year=document.academic_year,
    )
    parts = [header, content]
    return expand('\n\n'.join(part for part in parts if part))


def prepare_chunks(document, drafts):
    return [
        Chunk(
            document=document,
            chunk_index=index,
            content=draft.content,
            search_text=build_search_text(document, draft.content, draft.heading_path),
            heading_path=draft.heading_path[:500],
            page_start=draft.page_start,
            page_end=draft.page_end,
            token_count=draft.token_count,
            category=document.category,
            department=document.department,
            is_current=document.is_current,
        )
        for index, draft in enumerate(drafts)
    ]


def embed_chunks(llm, document, chunks):
    vectors = llm.embed_documents(
        [chunk.search_text for chunk in chunks], titles=[document.title] * len(chunks)
    )
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.embedding_model = llm.embed_model


def write_chunks(document, chunks, *, embedding_model):
    """Replace the document's chunks and mark it ready, in one transaction."""
    for chunk in chunks:
        chunk.is_searchable = True
    with transaction.atomic():
        Chunk.objects.filter(document=document).delete()
        Chunk.objects.bulk_create(chunks, batch_size=500)
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.READY,
            status_detail='',
            error='',
            chunk_count=len(chunks),
            token_count=sum(chunk.token_count for chunk in chunks),
            embedding_model=embedding_model,
            processed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        transaction.on_commit(lambda: knowledge_changed.send(sender=Document, document=document))


def load_source(document):
    """Raw bytes for a document, from storage or (for web pages) a fresh fetch."""
    if document.source_type == SourceType.URL:
        try:
            result = fetch(
                document.source_url, max_bytes=settings.INGEST_MAX_FILE_MB * 1024 * 1024
            )
        except (FetchError, UnsafeURLError) as exc:
            raise ProcessingError(f'Could not fetch the page: {exc}') from exc
        return result.content
    if not document.storage_path:
        raise ProcessingError('The original file is missing.')
    try:
        return get_storage().download(document.storage_path)
    except StorageError as exc:
        raise ProcessingError('Could not read the original file from storage.') from exc


def process_document(document_id, *, llm=None):
    """Extract, chunk, embed and publish one queued document."""
    document = claim(document_id)
    if document is None:
        return None
    llm = llm or get_llm()
    try:
        if document.source_type == SourceType.CRAWLER:
            # Imported chunks have no source file: rebuild search text and re-embed.
            drafts = [
                ChunkDraft(c.content, c.heading_path, c.page_start, c.page_end)
                for c in document.chunks.order_by('chunk_index')
            ]
            markdown = '\n\n'.join(draft.content for draft in drafts)
        else:
            progress(document, 'Extracting text')
            extracted = extract(
                load_source(document),
                document.source_type,
                max_pages=settings.INGEST_MAX_PAGES,
                url=document.source_url or None,
            )
            if extracted.title and not document.title:
                document.title = extracted.title[:300]
                Document.objects.filter(pk=document.pk).update(title=document.title)
            if extracted.page_count:
                Document.objects.filter(pk=document.pk).update(page_count=extracted.page_count)
            markdown = extracted.markdown
            drafts = build_chunks(markdown)
        if not drafts:
            raise ProcessingError('No text could be extracted from this document.')

        chunks = prepare_chunks(document, drafts)
        progress(document, f'Embedding {len(chunks)} chunks')
        embed_chunks(llm, document, chunks)
        write_chunks(document, chunks, embedding_model=llm.embed_model)
        logger.info('Document %s ready: %s chunks', document.pk, len(chunks))
    except (UnsupportedFile, ProcessingError) as exc:
        fail(document, str(exc))
    except QuotaExhausted:
        fail(document, 'The LLM provider quota is used up for today. Reprocess later.')
    except LLMError as exc:
        logger.warning('LLM failure while processing %s: %s', document.pk, exc)
        fail(document, 'The LLM provider is unavailable. Reprocess later.')
    except Exception:
        logger.exception('Unexpected failure while processing document %s', document.pk)
        fail(document, 'Unexpected error while processing. Check the server logs.')
    return Document.objects.get(pk=document.pk)


def fail(document, message):
    Document.objects.filter(pk=document.pk).update(
        status=DocumentStatus.FAILED,
        status_detail='',
        error=truncate(message, 500),
        updated_at=timezone.now(),
    )
