"""The nightly search-quality check."""

from datetime import timedelta
from types import SimpleNamespace

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from rag import quality
from rag.evaluation import CaseResult, Report
from rag.models import EvalRun


def report(ranks, *, important=()):
    results = []
    for index, rank in enumerate(ranks):
        case = {'id': f'case-{index}', 'question': 'q', 'answerable': True,
                'important': f'case-{index}' in important}
        results.append(CaseResult(case=case, rank=rank))
    return Report(results=results)


def run(recall, mrr, *, days_ago=0, important=()):
    item = EvalRun.objects.create(cases=10, recall_at_5=recall, recall_at_10=recall, mrr=mrr,
                                  important_misses=list(important))
    EvalRun.objects.filter(pk=item.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    item.refresh_from_db()
    return item


class RecordTests(TestCase):
    def test_record_scores_and_audits(self):
        llm = SimpleNamespace(chat_model='chat-x', fast_model='fast-x', embed_model='embed-x',
                              usage=SimpleNamespace(calls=42))
        saved = quality.record(report([1, 2, None, 7], important=('case-2',)), llm,
                               trigger='nightly', duration_ms=1234)
        self.assertEqual((saved.cases, saved.recall_at_5, saved.recall_at_10), (4, 0.5, 0.75))
        self.assertAlmostEqual(saved.mrr, round((1 + 0.5 + 1 / 7) / 4, 4))
        self.assertEqual(saved.misses, ['case-2', 'case-3'])
        self.assertEqual(saved.important_misses, ['case-2'])
        self.assertEqual(saved.models_used,
                         {'chat': 'chat-x', 'fast': 'fast-x', 'embed': 'embed-x'})
        self.assertEqual((saved.llm_calls, saved.trigger), (42, 'nightly'))
        event = AuditEvent.objects.get(action='eval.recorded')
        self.assertEqual((event.actor_kind, event.resource_id), ('service', str(saved.pk)))

    def test_record_refuses_partial_runs(self):
        with self.assertRaises(CommandError):
            call_command('eval_rag', '--record', 'manual', '--answers')


class WarningTests(TestCase):
    def codes(self):
        return [warning['code'] for warning in quality.summary()['warnings']]

    def test_no_runs_no_warnings(self):
        self.assertEqual(quality.summary(), {'latest': None, 'previous': None, 'warnings': []})

    def test_healthy_run(self):
        run(0.95, 0.9, days_ago=1)
        run(0.95, 0.92)
        self.assertEqual(self.codes(), [])
        self.assertEqual(quality.summary()['previous']['recall_at_5'], 0.95)

    def test_regressions(self):
        run(0.95, 0.95, days_ago=1)
        run(0.85, 0.8, important=('fees-hostel',))
        self.assertEqual(self.codes(), ['below_target', 'recall_dropped', 'mrr_dropped',
                                        'important_missed'])

    def test_stale(self):
        run(0.95, 0.9, days_ago=4)
        self.assertEqual(self.codes(), ['stale'])

    def test_stats_include_quality(self):
        run(0.95, 0.9)
        client = client_for(make_user('admin@thapar.edu', staff=True))
        data = client.get('/api/v1/admin/stats/').data
        self.assertEqual(data['quality']['latest']['recall_at_5'], 0.95)
        self.assertEqual(data['quality']['warnings'], [])
