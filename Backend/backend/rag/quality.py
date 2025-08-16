"""The nightly search-quality check: recording runs and warning on regressions."""

from datetime import timedelta

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from django.utils import timezone

from rag.models import EvalRun

TARGET_RECALL = 0.9
RECALL_DROP = 0.05
MRR_DROP = 0.1
STALE_DAYS = 3


def record(report, llm, *, trigger=EvalRun.Trigger.MANUAL, duration_ms=0):
    rows = report._answerable()
    run = EvalRun.objects.create(
        trigger=trigger,
        cases=len(report.results),
        recall_at_5=round(report.recall(5), 4),
        recall_at_10=round(report.recall(10), 4),
        mrr=round(report.mrr(), 4),
        errors=sum(1 for result in report.results if result.error),
        misses=[r.case['id'] for r in rows if not (r.rank and r.rank <= 5)],
        important_misses=report.important_misses(),
        models_used={
            'chat': getattr(llm, 'chat_model', ''),
            'fast': getattr(llm, 'fast_model', ''),
            'embed': getattr(llm, 'embed_model', ''),
        },
        llm_calls=getattr(getattr(llm, 'usage', None), 'calls', 0),
        duration_ms=duration_ms,
    )
    AuditEvent.objects.create(
        actor=None,
        actor_kind=AuditActorKind.SERVICE,
        action='eval.recorded',
        resource_type='eval_run',
        resource_id=str(run.pk),
        outcome=AuditOutcome.SUCCEEDED,
        metadata={'trigger': run.trigger, 'recall_at_5': run.recall_at_5, 'mrr': run.mrr},
    )
    return run


def _payload(run):
    if run is None:
        return None
    return {
        'id': run.pk,
        'created_at': run.created_at,
        'trigger': run.trigger,
        'cases': run.cases,
        'recall_at_5': run.recall_at_5,
        'recall_at_10': run.recall_at_10,
        'mrr': run.mrr,
        'errors': run.errors,
        'misses': run.misses,
        'important_misses': run.important_misses,
    }


def warnings_for(latest, previous, now=None):
    now = now or timezone.now()
    if latest is None:
        return []
    found = []
    if latest.recall_at_5 < TARGET_RECALL:
        found.append({'code': 'below_target',
                      'message': f'Recall@5 is {latest.recall_at_5:.2f}, below the '
                                 f'{TARGET_RECALL:.2f} target.'})
    if previous is not None:
        if previous.recall_at_5 - latest.recall_at_5 >= RECALL_DROP - 1e-9:
            found.append({'code': 'recall_dropped',
                          'message': f'Recall@5 fell from {previous.recall_at_5:.2f} to '
                                     f'{latest.recall_at_5:.2f} since the previous run.'})
        if previous.mrr - latest.mrr >= MRR_DROP - 1e-9:
            found.append({'code': 'mrr_dropped',
                          'message': f'MRR fell from {previous.mrr:.2f} to {latest.mrr:.2f} '
                                     'since the previous run.'})
    if latest.important_misses:
        found.append({'code': 'important_missed',
                      'message': 'Important questions missed: '
                                 + ', '.join(latest.important_misses) + '.'})
    if latest.errors:
        found.append({'code': 'errors',
                      'message': f'{latest.errors} question(s) failed to run.'})
    if latest.created_at < now - timedelta(days=STALE_DAYS):
        found.append({'code': 'stale',
                      'message': f'No check has run for over {STALE_DAYS} days.'})
    return found


def summary(now=None):
    """For the admin Overview: the latest run, the one before, and what needs attention."""
    latest, previous = (list(EvalRun.objects.order_by('-created_at')[:2]) + [None, None])[:2]
    return {
        'latest': _payload(latest),
        'previous': _payload(previous),
        'warnings': warnings_for(latest, previous, now),
    }
