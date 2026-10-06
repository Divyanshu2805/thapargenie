"""Import the thapar.edu crawler export (`chunks.jsonl.gz`).

The crawler already produced good chunks (tables kept whole, header rows repeated), so
they are used as they are: one Document per crawler record, one Chunk per row. Only
embedding happens here.

Resumable: a record whose content hash is already `ready` is skipped, so re-running
after an interruption (or after the daily embedding quota resets) continues where it
stopped. A record whose content changed replaces the old document.
"""

import gzip
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from common.text import estimate_tokens, normalize_text
from django.db import transaction
from django.utils import timezone

from knowledge.ingest.chunk import ChunkDraft, build_chunks
from knowledge.ingest.contextualize import BATCH, contextualize
from knowledge.ingest.pipeline import CONTEXTUALIZE_MAX_CHUNKS, prepare_chunks
from knowledge.models import Category, Chunk, Document, DocumentStatus, SourceType
from knowledge.signals import knowledge_changed

DEFAULT_CATEGORIES = (
    'about_contact',
    'academic_calendar',
    'admissions',
    'courses_syllabus',
    'departments',
    'faculty',
    'fees_scholarships',
    'hostel_campus_life',
    'notices',
    'placements',
    'rules_regulations',
)

_PAGE = re.compile(r'^\[\[?page\s+(\d+)\]\]?\s*$', re.IGNORECASE | re.MULTILINE)
_YEAR = re.compile(r'\b(20\d{2})\s*[-–/]\s*(\d{2})\b')
MAX_CONTENT_CHARS = 11_000


@dataclass
class Record:
    record_id: str
    metadata: dict
    rows: list = field(default_factory=list)

    @property
    def content_hash(self):
        digest = hashlib.sha256(f'crawler:{self.record_id}'.encode())
        for row in self.rows:
            digest.update(row['text'].encode())
        return digest.hexdigest()


def read_records(path, *, categories, include_review=False):
    """Group export rows by record, in export order, keeping only wanted ones."""
    statuses = {'keep', 'review'} if include_review else {'keep'}
    records = OrderedDict()
    with gzip.open(Path(path), 'rt', encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            meta = row.get('metadata') or {}
            if meta.get('category') not in categories or meta.get('status') not in statuses:
                continue
            record = records.setdefault(row['record_id'], Record(row['record_id'], meta))
            record.rows.append(row)
    for record in records.values():
        record.rows.sort(key=lambda r: r.get('chunk_index', 0))
    return list(records.values())


def _strip_header(text):
    """The crawler prefixes each chunk with 'Title | Dept | Category' and a blank line."""
    first, sep, rest = text.partition('\n\n')
    return rest if sep and ' | ' in first and '\n' not in first else text


def _drafts(record):
    drafts = []
    for row in record.rows:
        body = _strip_header(row['text'])
        pages = [int(n) for n in _PAGE.findall(body)]
        content = normalize_text(_PAGE.sub('', body))
        if not content:
            continue
        if len(content) > MAX_CONTENT_CHARS:
            drafts += build_chunks(content)
            continue
        drafts.append(
            ChunkDraft(content, '', min(pages) if pages else None, max(pages) if pages else None)
        )
    return drafts


def _academic_year(title):
    match = _YEAR.search(title or '')
    if not match:
        return ''
    start, end = match.groups()
    return f'{start}-{end}' if int(end) == (int(start) + 1) % 100 else ''


def _effective_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def build_document(record):
    meta = record.metadata
    url = meta.get('url') or ''
    return Document(
        title=(meta.get('title') or url or record.record_id)[:300],
        source_type=SourceType.CRAWLER,
        source_url=url[:2000] if url.startswith('https://') else '',
        content_hash=record.content_hash,
        category=meta['category'] if meta.get('category') in Category.values else 'other',
        department=(meta.get('department') or '')[:120],
        academic_year=_academic_year(meta.get('title')),
        effective_date=_effective_date(meta.get('date')),
        is_current=meta.get('is_current') is not False,
        status=DocumentStatus.PROCESSING,
        status_detail='Importing',
        metadata={
            'record_id': record.record_id,
            'type': meta.get('type'),
            'file_type': meta.get('file_type'),
            'effective_year': meta.get('effective_year'),
        },
    )


@dataclass
class ImportStats:
    records: int = 0
    skipped: int = 0
    imported: int = 0
    replaced: int = 0
    chunks: int = 0
    empty: int = 0


def plan_import(records):
    """Split records into (to_import, stats) without touching the embedding API."""
    stats = ImportStats(records=len(records))
    ready = set(
        Document.objects.filter(
            source_type=SourceType.CRAWLER, status=DocumentStatus.READY
        ).values_list('content_hash', flat=True)
    )
    pending = []
    for record in records:
        if record.content_hash in ready:
            stats.skipped += 1
        else:
            pending.append(record)
    return pending, stats


def _save(document, chunks, embedding_model, stats):
    record_id = document.metadata['record_id']
    with transaction.atomic():
        # Replace an older version of the same record, or a half-finished attempt.
        stale = Document.objects.filter(
            source_type=SourceType.CRAWLER, metadata__record_id=record_id
        )
        if stale.exclude(content_hash=document.content_hash).exists():
            stats.replaced += 1
        stale.delete()
        document.status = DocumentStatus.READY
        document.status_detail = ''
        document.chunk_count = len(chunks)
        document.token_count = sum(c.token_count for c in chunks)
        document.embedding_model = embedding_model
        document.processed_at = timezone.now()
        document.save()
        for chunk in chunks:
            chunk.document = document
            chunk.is_searchable = True
        Chunk.objects.bulk_create(chunks, batch_size=500)


def _contexts(llm, document, drafts):
    """One sentence per chunk saying what it belongs to (None for pages too long to read)."""
    if len(drafts) > CONTEXTUALIZE_MAX_CHUNKS:
        return None
    return contextualize(
        llm,
        title=document.title,
        document_text='\n\n'.join(draft.content for draft in drafts),
        contents=[draft.content for draft in drafts],
        strict=True,
    )


def import_records(records, llm, *, batch_texts=200, progress=None, contextualise=False):
    """Embed and store records. Embeddings are batched across records to save requests.

    Raises whatever the LLM raises (e.g. QuotaExhausted) after saving completed work.
    With `contextualise`, each page's chunks also get a sentence saying what they belong to
    (one fast-model call per 10 chunks), so "Hostel L" is found as "Viyat Hall".
    """
    pending, stats = plan_import(records)
    queue = []
    queued_texts = 0

    def flush():
        nonlocal queue, queued_texts
        if not queue:
            return
        all_chunks = [chunk for _, chunks in queue for chunk in chunks]
        # One call per `llm.embed_batch_size` texts across all queued records.
        vectors = llm.embed_documents(
            [chunk.search_text for chunk in all_chunks],
            titles=[document.title for document, chunks in queue for _ in chunks],
        )
        for chunk, vector in zip(all_chunks, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model = llm.embed_model
        for document, chunks in queue:
            _save(document, chunks, llm.embed_model, stats)
            stats.imported += 1
            stats.chunks += len(chunks)
        if progress:
            progress(stats, len(pending))
        queue, queued_texts = [], 0

    try:
        for record in pending:
            drafts = _drafts(record)
            if not drafts:
                stats.empty += 1
                continue
            document = build_document(record)
            contexts = _contexts(llm, document, drafts) if contextualise else None
            chunks = prepare_chunks(document, drafts, contexts)
            queue.append((document, chunks))
            queued_texts += len(chunks)
            if queued_texts >= batch_texts:
                flush()
        flush()
    finally:
        if stats.imported:
            knowledge_changed.send(sender=Document)
    return stats


def estimate(records):
    texts = sum(len(_drafts(record)) for record in records)
    tokens = sum(estimate_tokens(row['text']) for record in records for row in record.rows)
    return texts, tokens


def estimate_context_calls(records):
    """Fast-model calls `contextualise` would make: one per 10 chunks of each readable page."""
    calls = 0
    for record in records:
        count = len(_drafts(record))
        if 0 < count <= CONTEXTUALIZE_MAX_CHUNKS:
            calls += -(-count // BATCH)
    return calls

