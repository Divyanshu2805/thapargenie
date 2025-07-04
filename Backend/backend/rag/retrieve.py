"""Hybrid retrieval: pgvector similarity + Postgres full-text search, fused with RRF.

The vector lists (one per query phrasing) come back in one SQL round trip; the keyword
list is a second query that runs while the queries are embedded. Reciprocal rank fusion
then merges them; it only looks at ranks, so cosine distances and ts_rank scores never
need to be put on the same scale.

Boosts from query analysis (category, current, academic year) are soft and bounded:
each adds at most BOOST x the best fused score, so they reorder close candidates but
can never pull an irrelevant chunk above a clearly relevant one.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from common.db import HNSW_EF_SEARCH
from django.conf import settings
from django.db import InterfaceError, OperationalError, connection, transaction
from knowledge.models import Chunk

from rag.aliases import expansions

RRF_K = 60
LIST_SIZE = 40
BOOST = 0.10
DUPLICATE_OVERLAP = 0.85

_TOKEN = re.compile(r'[a-z0-9]+')


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
    boost: float = 0.0
    rerank_score: float | None = None

    @property
    def score(self):
        return self.fused + self.boost

    def trace(self):
        return {
            'chunk_id': self.chunk_id,
            'title': self.title,
            'heading_path': self.heading_path,
            'ranks': self.ranks,
            'fused': round(self.fused, 5),
            'boost': round(self.boost, 5),
            'rerank': self.rerank_score,
        }


def vector_literal(vector):
    return '[' + ','.join(f'{value:.6f}' for value in vector) + ']'


def keyword_query(text):
    """OR-query of normalised words. Postgres drops stop words and stems the rest.

    OR (not AND) keeps recall high for conversational questions; ts_rank_cd still
    ranks chunks that match more of the words higher.
    """
    words = []
    for word in _TOKEN.findall(text.lower()):
        if word not in words:
            words.append(word)
    return ' | '.join(words[:40])


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


def keyword_list(keywords, *, size=LIST_SIZE):
    """Chunk ids best first for the full-text OR query (empty if no usable words).

    Broad OR queries match (and score) a large share of the corpus, so this is the
    slowest part of retrieval (~0.5 s on the dev corpus); it does not need the query
    embeddings, so `KeywordSearch` starts it while they are computed.
    """
    tsquery = keyword_query(keywords)
    if not tsquery:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM knowledge_chunk, to_tsquery('english', %s) q "
            'WHERE is_searchable AND fts @@ q ORDER BY ts_rank_cd(fts, q, 1) DESC LIMIT %s',
            [tsquery, size],
        )
        return [str(row[0]) for row in cursor.fetchall()]


def _keyword_list_in_thread(keywords):
    # A pool thread keeps its own connection between searches; if the server dropped
    # it while idle, reconnect once.
    try:
        return keyword_list(keywords)
    except (InterfaceError, OperationalError):
        connection.close()
        return keyword_list(keywords)


_keyword_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='keyword-search')


class KeywordSearch:
    """The keyword list for one analysis, started as early as possible.

    With RETRIEVE_PARALLEL it runs on a small thread pool (its own DB connection) while
    the caller embeds the queries. Tests turn it off: a pool thread cannot see a test
    transaction, so there it runs when the result is first asked for.
    """

    def __init__(self, analysis):
        self.text = keyword_text(analysis)
        self._future = (_keyword_executor.submit(_keyword_list_in_thread, self.text)
                        if settings.RETRIEVE_PARALLEL else None)

    def result(self):
        return self._future.result() if self._future else keyword_list(self.text)


def ranked_lists(vectors, keywords, *, size=LIST_SIZE):
    """{list_name: [chunk_id, ...best first]} for each query vector and the keywords."""
    lists = vector_lists(vectors, size=size)
    ids = keyword_list(keywords, size=size)
    if ids:
        lists['keyword'] = ids
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


def apply_boosts(candidates, analysis):
    if not candidates:
        return
    top = max(candidate.fused for candidate in candidates)
    for candidate in candidates:
        boost = 0.0
        if analysis.categories and candidate.category in analysis.categories:
            boost += BOOST
        if analysis.needs_current and candidate.is_current:
            boost += BOOST
        if analysis.academic_year and candidate.academic_year == analysis.academic_year:
            boost += BOOST
        candidate.boost = boost * top


# Words that occur in nearly every document of a single-institution corpus.
_INSTITUTE = re.compile(
    r'(thapar\s+institute\s+of\s+engineering\s+(and|&)\s+technology|thapar\s+university'
    r'|thapar\s+institute|tiet|thapar)',
    re.IGNORECASE,
)


def keyword_text(analysis):
    base = ' '.join(filter(None, [analysis.keywords, analysis.standalone_query]))
    base = _INSTITUTE.sub(' ', base)
    return ' '.join([base, *expansions(base)])


@dataclass
class Retrieval:
    candidates: list
    lists: dict

    def trace(self):
        return {
            'lists': {name: len(ids) for name, ids in self.lists.items()},
            'candidates': [candidate.trace() for candidate in self.candidates],
        }


def retrieve(llm, analysis, *, vectors=None, keywords=None, limit=25):
    """`keywords` is a KeywordSearch started earlier (the pipeline starts it before it
    embeds the queries); without one it is started here, before embedding."""
    keywords = keywords or KeywordSearch(analysis)
    if vectors is None:
        queries = analysis.search_queries
        vectors = llm.embed_queries(queries) if queries else []
    lists = vector_lists(vectors)
    keyword_ids = keywords.result()
    if keyword_ids:
        lists['keyword'] = keyword_ids
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
    apply_boosts(candidates, analysis)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return Retrieval(drop_near_duplicates(candidates)[:limit], lists)


def _words(text):
    return set(_TOKEN.findall(text.lower()))


def drop_near_duplicates(candidates, threshold=DUPLICATE_OVERLAP):
    """Keep the best-ranked copy of content published more than once (same PDF at two
    URLs, a page and its PDF). Duplicates would otherwise crowd out other sources."""
    kept, kept_words = [], []
    for candidate in candidates:
        words = _words(candidate.content)
        duplicate = any(
            len(words & other) / max(1, len(words | other)) >= threshold for other in kept_words
        )
        if not duplicate:
            kept.append(candidate)
            kept_words.append(words)
    return kept
