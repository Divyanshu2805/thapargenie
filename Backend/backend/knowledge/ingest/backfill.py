"""Add context sentences to documents that were stored without them.

The crawler import used the chunks as they came, so a chunk that says only "Hostel L" has
no link to "Viyat Hall". Re-importing everything would repeat all the embedding work;
this reads each stored page once, writes the context sentences and re-embeds just the
chunks that changed. Chunk text shown to students is untouched: the sentence goes into
`search_text` only (see contextualize.py).

Safe to stop and run again: a chunk that already has context is left alone.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from knowledge.ingest.contextualize import BATCH, contextualize
from knowledge.ingest.pipeline import CONTEXTUALIZE_MAX_CHUNKS, build_search_text
from knowledge.models import Chunk, Document, DocumentStatus
from knowledge.signals import knowledge_changed


@dataclass
class BackfillStats:
    documents: int = 0
    chunks: int = 0
    already_done: int = 0
    too_long: int = 0
    model_calls: int = 0


def needs_context(document, chunk):
    """True when the chunk's search text is just the header and the content."""
    return chunk.search_text == build_search_text(document, chunk.content, chunk.heading_path)


def _pending(documents):
    for document in documents:
        chunks = list(document.chunks.order_by('chunk_index'))
        yield document, chunks, [c for c in chunks if needs_context(document, c)]


def _documents(title_contains=''):
    documents = Document.objects.filter(status=DocumentStatus.READY, chunk_count__gt=0)
    if title_contains:
        documents = documents.filter(title__icontains=title_contains)
    return documents.order_by('created_at')


def backfill_context(llm, *, limit=None, title_contains='', dry_run=False, progress=None):
    """Returns BackfillStats. With `dry_run` nothing is called or saved; the counts are what
    a real run would do (`model_calls` is the number of fast-model calls it would make).

    Raises whatever the LLM raises (e.g. QuotaExhausted) after saving finished documents.
    """
    stats = BackfillStats()
    changed = False
    try:
        for document, chunks, todo in _pending(_documents(title_contains)):
            if limit is not None and stats.documents >= limit:
                break
            if not todo:
                stats.already_done += 1
                continue
            if len(chunks) > CONTEXTUALIZE_MAX_CHUNKS:
                stats.too_long += 1
                continue
            stats.documents += 1
            stats.chunks += len(todo)
            stats.model_calls += -(-len(chunks) // BATCH)
            if dry_run:
                continue
            if _write_context(llm, document, chunks, todo):
                changed = True
            if progress:
                progress(stats)
    finally:
        if changed:
            knowledge_changed.send(sender=Document)
    return stats


def _write_context(llm, document, chunks, todo):
    contexts = contextualize(
        llm,
        title=document.title,
        document_text='\n\n'.join(chunk.content for chunk in chunks),
        contents=[chunk.content for chunk in chunks],
        strict=True,
    )
    wanted = {chunk.pk for chunk in todo}
    updates = [
        (chunk, build_search_text(document, chunk.content, chunk.heading_path, context))
        for chunk, context in zip(chunks, contexts, strict=True)
        if chunk.pk in wanted and context
    ]
    if not updates:
        return False
    vectors = llm.embed_documents(
        [text for _, text in updates], titles=[document.title] * len(updates)
    )
    now = timezone.now()
    for (chunk, text), vector in zip(updates, vectors, strict=True):
        chunk.search_text = text
        chunk.embedding = vector
        chunk.embedding_model = llm.embed_model
        chunk.updated_at = now
    with transaction.atomic():
        Chunk.objects.bulk_update(
            [chunk for chunk, _ in updates],
            ['search_text', 'embedding', 'embedding_model', 'updated_at'],
        )
    return True
