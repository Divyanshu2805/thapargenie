"""Vector search over document chunks with pgvector.

Each query phrasing gets its own nearest-neighbour list, all in one SQL round trip.
Reciprocal rank fusion merges the lists; it only looks at ranks, so a chunk that is near
the top for several phrasings beats one that is close for a single phrasing.
"""

from dataclasses import dataclass, field

from common.db import HNSW_EF_SEARCH
from django.conf import settings
from django.db import connection, transaction
from knowledge.models import Chunk

RRF_K = 60
LIST_SIZE = 40


@dataclass
class Candidate:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    heading_path: str
    page_start: int | None
    page_end: int | None
    title: str
    url: str
    category: str
    academic_year: str
    is_current: bool
    source_type: str
    storage_path: str
    ranks: dict = field(default_factory=dict)
    fused: float = 0.0

    @property
    def score(self):
        return self.fused

    def trace(self):
        return {
            'chunk_id': self.chunk_id,
            'title': self.title,
            'heading_path': self.heading_path,
            'ranks': self.ranks,
            'fused': round(self.fused, 5),
        }


def vector_literal(vector):
    return '[' + ','.join(f'{value:.6f}' for value in vector) + ']'


def vector_lists(vectors, *, size=LIST_SIZE):
    """{'vector:N': [chunk_id, ...best first]} for each query vector, in one round trip.

    The SQL text is assembled only from the fixed fragments below and an integer loop
    index; every value (vectors, limits) is a bound parameter.
    """
    parts, params = [], []
    for index, vector in enumerate(vectors):
        literal = vector_literal(vector)
        parts.append(
            f"(SELECT 'vector:{index:d}' AS list, id, embedding <=> %s::halfvec AS distance "  # noqa: S608
            'FROM knowledge_chunk WHERE is_searchable '
            'ORDER BY embedding <=> %s::halfvec LIMIT %s)'
        )
        params += [literal, literal, size]
    if not parts:
        return {}
    sql = 'SELECT * FROM (' + ' UNION ALL '.join(parts) + ') AS lists ORDER BY 1, 3'  # noqa: S608
    if settings.DATABASE_TRANSACTION_POOLING:
        # No session settings with a transaction pooler (common/db.py): set them for
        # this query's transaction instead (two extra round trips).
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('hnsw.ef_search', %s, true), "
                "set_config('hnsw.iterative_scan', 'relaxed_order', true)",
                [str(HNSW_EF_SEARCH)],
            )
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    else:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    lists = {}
    for name, chunk_id, _distance in rows:
        lists.setdefault(name, []).append(str(chunk_id))
    return lists


def fuse(lists, k=RRF_K):
    """Reciprocal rank fusion: sum of 1 / (k + rank) over every list a chunk appears in."""
    scores, ranks = {}, {}
    for name, ids in lists.items():
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(chunk_id, {})[name] = rank
    return scores, ranks


def load_candidates(chunk_ids):
    chunks = (
        Chunk.objects.filter(pk__in=chunk_ids)
        .select_related('document')
        .only(
            'id', 'chunk_index', 'content', 'heading_path', 'page_start', 'page_end',
            'category', 'is_current', 'document__id', 'document__title',
            'document__source_url', 'document__academic_year', 'document__source_type',
            'document__storage_path',
        )
    )
    return {
        str(chunk.pk): Candidate(
            chunk_id=str(chunk.pk),
            document_id=str(chunk.document_id),
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            heading_path=chunk.heading_path,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            title=chunk.document.title,
            url=chunk.document.source_url,
            category=chunk.category,
            academic_year=chunk.document.academic_year,
            is_current=chunk.is_current,
            source_type=chunk.document.source_type,
            storage_path=chunk.document.storage_path,
        )
        for chunk in chunks
    }


@dataclass
class Retrieval:
    candidates: list
    lists: dict

    def trace(self):
        return {
            'lists': {name: len(ids) for name, ids in self.lists.items()},
            'candidates': [candidate.trace() for candidate in self.candidates],
        }


def retrieve(llm, analysis, *, vectors=None, limit=25):
    if vectors is None:
        queries = analysis.search_queries
        vectors = llm.embed_queries(queries) if queries else []
    lists = vector_lists(vectors)
    scores, ranks = fuse(lists)
    best = sorted(scores, key=scores.get, reverse=True)[: limit * 2]
    loaded = load_candidates(best)
    candidates = []
    for chunk_id in best:
        candidate = loaded.get(chunk_id)
        if candidate is None:
            continue
        candidate.fused = scores[chunk_id]
        candidate.ranks = ranks[chunk_id]
        candidates.append(candidate)
    return Retrieval(candidates[:limit], lists)
