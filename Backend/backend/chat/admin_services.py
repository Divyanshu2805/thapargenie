"""Admin insight and control over chat: stats, feedback triage, gaps, settings, playground.

Privacy: admins never browse conversations. Feedback shows only the
rated Q&A pair, with the student replaced by a stable pseudonym; gaps show only grouped
queries and counts.
"""

import hashlib
import hmac
from datetime import datetime, time, timedelta

from common.audit import audit
from django.conf import settings as django_settings
from django.db import connection, transaction
from django.db.models import Count, Func, Max, Q, Sum, TextField, Value
from django.db.models.functions import Coalesce, Lower, NullIf, Trim
from django.utils import timezone
from knowledge.models import Chunk, Document
from rag.llm import get_llm
from rag.pipeline import answer_events

from chat import quota
from chat.models import AnswerCache, ChatSettings, Feedback, Message, UsageDaily

RANGES = {'7d': 7, '30d': 30}
GAP_LIMIT = 100


def since(days):
    """Start of the first day of a range that ends today (inclusive)."""
    first_day = timezone.localdate() - timedelta(days=days - 1)
    return first_day, timezone.make_aware(datetime.combine(first_day, time.min))


def pseudonym(user_id):
    """A stable, non-reversible handle for grouping feedback by student."""
    key = django_settings.SECRET_KEY.encode()
    return hmac.new(key, f'feedback:{user_id}'.encode(), hashlib.sha256).hexdigest()[:12]


# -- stats ---------------------------------------------------------------------------

USAGE_FIELDS = ('questions', 'answers', 'cached', 'llm_calls', 'prompt_tokens',
                'completion_tokens')


def _latency(start):
    table = Message._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
              percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),
              percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms),
              percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
                FILTER (WHERE answer_type <> 'cached'),
              percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                FILTER (WHERE answer_type <> 'cached')
            FROM {table}
            WHERE role = 'assistant' AND status = 'complete'
              AND latency_ms IS NOT NULL AND created_at >= %s
            """,  # noqa: S608 - the table name comes from the model, not from input
            [start],
        )
        row = cursor.fetchone()
    values = [round(value) if value is not None else None for value in row]
    return {'p50_ms': values[0], 'p95_ms': values[1],
            'uncached_p50_ms': values[2], 'uncached_p95_ms': values[3]}


def stats(days):
    first_day, start = since(days)
    usage = UsageDaily.objects.filter(day__gte=first_day)
    totals = usage.aggregate(**{name: Coalesce(Sum(name), 0) for name in USAGE_FIELDS})
    per_day = {
        row['day']: row
        for row in usage.values('day').annotate(**{name: Sum(name) for name in USAGE_FIELDS})
    }
    daily = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        row = per_day.get(day, {})
        daily.append({'day': day.isoformat(),
                      **{name: row.get(name) or 0 for name in USAGE_FIELDS}})

    answer_types = dict(
        Message.objects.filter(role=Message.Role.ASSISTANT, created_at__gte=start)
        .exclude(answer_type=None)
        .values_list('answer_type')
        .annotate(count=Count('id'))
    )
    ratings = Feedback.objects.filter(created_at__gte=start).aggregate(
        up=Count('id', filter=Q(rating=1)), down=Count('id', filter=Q(rating=-1))
    )
    open_reviews = Feedback.objects.filter(rating=-1, review_status=Feedback.Review.OPEN).count()
    chat_settings = ChatSettings.load()
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_database_size(current_database())')
        database_bytes = cursor.fetchone()[0]

    return {
        'range_days': days,
        'totals': totals,
        'daily': daily,
        'answer_types': answer_types,
        'cache_hit_rate': round(totals['cached'] / totals['answers'], 3)
        if totals['answers'] else None,
        'feedback': {**ratings, 'open_reviews': open_reviews},
        'latency': _latency(start),
        'budget': {
            'llm_calls_today': quota.global_calls_today(),
            'global_daily_llm_calls': chat_settings.global_daily_llm_calls,
        },
        'knowledge': {
            'documents_by_status': dict(
                Document.objects.values_list('status').annotate(count=Count('id'))
            ),
            'documents_by_category': dict(
                Document.objects.values_list('category').annotate(count=Count('id'))
            ),
            'chunks': Chunk.objects.count(),
            'searchable_chunks': Chunk.objects.filter(is_searchable=True).count(),
            'cache_entries': AnswerCache.objects.filter(expires_at__gt=timezone.now()).count(),
        },
        'database_bytes': database_bytes,
    }


# -- feedback ------------------------------------------------------------------------

def feedback_queryset(*, review_status=None, rating=None, answer_type=None, reason=None):
    items = Feedback.objects.select_related(
        'message', 'message__parent', 'message__trace'
    ).prefetch_related('message__sources')
    if review_status:
        items = items.filter(review_status=review_status)
    if rating:
        items = items.filter(rating=rating)
    if answer_type:
        items = items.filter(message__answer_type=answer_type)
    if reason:
        items = items.filter(reason=reason)
    return items


def feedback_payload(feedback):
    """One rated Q&A pair. Never includes the student's email, id or conversation."""
    answer = feedback.message
    question = answer.parent
    trace = getattr(answer, 'trace', None)
    return {
        'id': str(feedback.pk),
        'rating': feedback.rating,
        'reason': feedback.reason,
        'comment': feedback.comment,
        'review_status': feedback.review_status,
        'admin_note': feedback.admin_note,
        'reviewed_at': feedback.reviewed_at,
        'created_at': feedback.created_at,
        'reporter': pseudonym(feedback.user_id),
        'question': question.content if question else '',
        'answer': {
            'content': answer.content,
            'answer_type': answer.answer_type,
            'grounded': answer.grounded,
            'model': answer.model,
            'latency_ms': answer.latency_ms,
            'created_at': answer.created_at,
            'sources': [
                {
                    'position': source.position,
                    'title': source.title,
                    'url': source.url,
                    'heading_path': source.heading_path,
                    'cited': source.cited,
                    'score': source.score,
                    'document_id': str(source.document_id) if source.document_id else None,
                    'chunk_id': str(source.chunk_id) if source.chunk_id else None,
                }
                for source in sorted(answer.sources.all(), key=lambda s: s.position)
            ],
        },
        'trace': {
            'standalone_query': trace.standalone_query,
            'analysis': trace.analysis,
            'retrieval': trace.retrieval,
            'timings': trace.timings,
        } if trace else None,
    }


def _apply_review(model, pk, changes, *, user, request_id, action, target):
    """Set review status and note on a feedback row, recording who did it; audited."""
    item = model.objects.select_for_update().get(pk=pk)
    fields = []
    for name in ('review_status', 'admin_note'):
        if name in changes and getattr(item, name) != changes[name]:
            setattr(item, name, changes[name])
            fields.append(name)
    if fields:
        item.reviewed_by = user
        item.reviewed_at = timezone.now()
        item.save(update_fields=[*fields, 'reviewed_by', 'reviewed_at', 'updated_at'])
        audit(user, action, target, item.pk, request_id=request_id,
              review_status=item.review_status, fields=fields)
    return item


@transaction.atomic
def review_feedback(feedback, changes, *, user, request_id=None):
    return _apply_review(Feedback, feedback.pk, changes, user=user, request_id=request_id,
                         action='feedback.reviewed', target='feedback')


# -- gaps ----------------------------------------------------------------------------

def _normalized(expression):
    """Lower-case with runs of whitespace collapsed, so trivial variants group together."""
    collapsed = Func(Lower(expression), Value(r'\s+'), Value(' '), Value('g'),
                     function='REGEXP_REPLACE', output_field=TextField())
    return Trim(collapsed)


def gaps(days):
    """Questions that got no answer, grouped by their normalised standalone query."""
    _, start = since(days)
    rows = (
        Message.objects.filter(
            role=Message.Role.ASSISTANT,
            answer_type=Message.AnswerType.NO_ANSWER,
            created_at__gte=start,
        )
        .annotate(query=_normalized(Coalesce(
            NullIf('trace__standalone_query', Value('', output_field=TextField())),
            'parent__content',
        )))
        .values('query')
        .annotate(
            count=Count('id'),
            askers=Count('conversation__user', distinct=True),
            last_seen=Max('created_at'),
        )
        .order_by('-count', '-last_seen')[:GAP_LIMIT]
    )
    return [
        {'query': row['query'] or '', 'count': row['count'],
         'askers': row['askers'], 'last_seen': row['last_seen']}
        for row in rows
    ]


# -- settings ------------------------------------------------------------------------

SETTINGS_FIELDS = (
    'daily_question_limit', 'global_daily_llm_calls', 'rerank_enabled', 'cache_enabled',
    'contextualize_default', 'auto_title_enabled', 'maintenance_mode', 'maintenance_message',
    'banner_text', 'starter_questions',
)
# Values safe to copy into the audit log (no free text).
AUDITED_VALUES = {
    'daily_question_limit', 'global_daily_llm_calls', 'rerank_enabled', 'cache_enabled',
    'contextualize_default', 'auto_title_enabled', 'maintenance_mode',
}


@transaction.atomic
def update_settings(changes, *, user, request_id=None):
    current = ChatSettings.load(fresh=True)
    current = ChatSettings.objects.select_for_update().get(pk=current.pk)
    changed = {}
    for name in SETTINGS_FIELDS:
        if name in changes and getattr(current, name) != changes[name]:
            changed[name] = (getattr(current, name), changes[name])
            setattr(current, name, changes[name])
    if not changed:
        return current
    current.updated_by = user
    current.save()
    audit(user, 'settings.updated', 'chat_settings', current.pk, request_id=request_id,
          fields=sorted(changed),
          values={name: list(pair) for name, pair in changed.items()
                  if name in AUDITED_VALUES})
    return current


# -- playground ----------------------------------------------------------------------

def playground(question, *, user, history=(), rerank_enabled=None):
    """Run the whole answer pipeline and return everything it did. Saves no content;
    only the LLM call counters are recorded, so the global budget stays accurate."""
    if rerank_enabled is None:
        rerank_enabled = ChatSettings.load().rerank_enabled
    llm = get_llm()
    statuses, result = [], None
    try:
        for event, data in answer_events(question, llm=llm, history=history,
                                         rerank_enabled=rerank_enabled):
            if event == 'status':
                statuses.append(data)
            elif event == 'done':
                result = data
    finally:
        quota.record_calls(user, llm.usage)
    return {
        'analysis': result.analysis.as_dict(),
        'stages': statuses,
        'retrieval': result.retrieval_trace,
        'reranked': result.reranked,
        'sources': [
            {
                **source.public(),
                'document_id': source.document_id,
                'chunk_ids': source.chunk_ids,
                'score': source.score,
                'is_current': source.is_current,
                'content': source.content,
                'cited': source.number in result.cited,
            }
            for source in result.sources
        ],
        'answer': result.text,
        'answer_type': result.answer_type,
        'grounded': result.grounded,
        'unsupported': result.unsupported,
        'model': result.model,
        'timings': result.timings,
        'usage': {
            'llm_calls': llm.usage.calls,
            'prompt_tokens': llm.usage.prompt_tokens,
            'completion_tokens': llm.usage.completion_tokens,
        },
    }
