"""Semantic answer cache for first-turn questions.

Students ask the same things ("hostel fee 2026-27") in many phrasings. The first question
of a chat whose embedding is within MAX_DISTANCE (cosine) of a cached question gets the
stored answer and citations instantly. The lookup runs in parallel with query analysis, so
a hit skips analysis, retrieval and generation, and a miss costs no extra time.

Safety: only grounded, cited, first-turn answers are stored; the whole cache is emptied
whenever the knowledge base changes; entries expire after TTL; a thumbs-down removes it.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from chat.models import AnswerCache

MAX_DISTANCE = 0.03  # cosine similarity >= 0.97
TTL = timedelta(days=7)


@dataclass
class CacheHit:
    entry_id: str
    text: str
    model: str
    sources: list


class Cache:
    def lookup(self, vector):
        entry = (
            AnswerCache.objects.filter(expires_at__gt=timezone.now())
            .annotate(distance=CosineDistance('query_embedding', vector))
            .filter(distance__lte=MAX_DISTANCE)
            .order_by('distance')
            .first()
        )
        if entry is None:
            return None
        AnswerCache.objects.filter(pk=entry.pk).update(
            hits=entry.hits + 1, last_hit_at=timezone.now()
        )
        return CacheHit(str(entry.pk), entry.answer, entry.model, entry.sources)


def source_rows(result):
    """Serializable rows for MessageSource, from a pipeline AnswerResult."""
    rows = []
    for source in result.sources:
        rows.append({
            **source.public(),
            'chunk_id': source.chunk_ids[0] if source.chunk_ids else None,
            'document_id': source.document_id,
            'cited': source.number in result.cited,
            'score': source.score,
        })
    return rows


def eligible(result, *, first_turn):
    return (
        first_turn
        and result.answer_type == 'answered'
        and result.grounded is True
        and result.query_vector is not None
        and bool(result.cited)
    )


def store(result):
    AnswerCache.objects.create(
        query_text=result.analysis.question[:1000],
        query_embedding=result.query_vector,
        answer=result.text,
        sources=source_rows(result),
        model=result.model,
        expires_at=timezone.now() + TTL,
    )


def forget_answer(text):
    """Called on thumbs-down: never serve this answer from the cache again."""
    AnswerCache.objects.filter(answer=text).delete()


def clear():
    transaction.on_commit(lambda: AnswerCache.objects.all().delete())

