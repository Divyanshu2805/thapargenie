"""CSV exports for the admin."""

import csv
import io
from unittest import mock

from api.models import AuditEvent
from common.csv_export import safe_cell
from common.tests.helpers import client_for, make_user
from common.throttles import AdminExportThrottle
from django.core.cache import cache
from django.utils import timezone

from chat.admin_services import pseudonym
from chat.models import Feedback, MessageSource, UsageDaily
from chat.tests.test_admin_api import BASE, AdminChatTestCase


def read_csv(response):
    text = b''.join(response.streaming_content if response.streaming else [response.content])
    return list(csv.reader(io.StringIO(text.decode('utf-8-sig'))))


class SafeCellTests(AdminChatTestCase):
    def test_formula_like_text_is_neutralised(self):
        for text in ('=HYPERLINK("x")', '+1', '-2+3', '@SUM(A1)', '\tx', '\rx'):
            self.assertEqual(safe_cell(text), f"'{text}")
        self.assertEqual(safe_cell('Hostel fee'), 'Hostel fee')
        self.assertEqual(safe_cell(-1), -1)
        self.assertEqual(safe_cell(None), '')
        self.assertEqual(safe_cell(True), 'yes')


class ExportTests(AdminChatTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_feedback_export_is_pseudonymous(self):
        reply = self.turn('=cmd|calc What is the hostel fee?')
        MessageSource.objects.create(message=reply, position=1, title='Fee notice', cited=True)
        Feedback.objects.create(message=reply, user=self.student, rating=-1, reason='outdated',
                                comment='Old numbers')
        other = self.turn('Library hours?')
        Feedback.objects.create(message=other, user=self.student, rating=1)

        response = self.client.get(f'{BASE}/feedback/export/', {'rating': '-1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="thapargenie-feedback-',
                      response['Content-Disposition'])
        rows = read_csv(response)
        self.assertEqual(rows[0][:4], ['rated_at', 'reporter', 'rating', 'reason'])
        self.assertEqual(len(rows), 2)
        row = dict(zip(rows[0], rows[1], strict=True))
        self.assertEqual(row['reporter'], pseudonym(self.student.pk))
        self.assertEqual(row['rating'], '-1')
        self.assertEqual(row['question'], "'=cmd|calc What is the hostel fee?")
        self.assertEqual(row['sources'], 'Fee notice')
        self.assertNotIn(self.student.email, response.content.decode())

        event = AuditEvent.objects.get(action='export.csv')
        self.assertEqual((event.resource_id, event.metadata['rows']), ('feedback', 1))
        self.assertEqual(event.metadata['filters'], {'rating': '-1'})

    def test_gaps_and_stats_exports(self):
        self.turn('Is there a swimming pool?', answer='No info.', answer_type='no_answer')
        UsageDaily.objects.create(user=self.student, day=timezone.localdate(), questions=3,
                                  answers=3, llm_calls=7)

        gaps = read_csv(self.client.get(f'{BASE}/gaps/export/', {'range': '7d'}))
        self.assertEqual(gaps[0], ['question', 'times_asked', 'students', 'last_asked'])
        self.assertEqual(gaps[1][:3], ['is there a swimming pool?', '1', '1'])

        stats = read_csv(self.client.get(f'{BASE}/stats/export/'))
        self.assertEqual(stats[0][:3], ['day', 'questions', 'answers'])
        self.assertEqual(len(stats), 8)
        self.assertEqual(stats[-1][:4], [timezone.localdate().isoformat(), '3', '3', '0'])

    def test_bad_filters_and_students(self):
        self.assertEqual(self.client.get(f'{BASE}/gaps/export/', {'range': '1y'}).status_code, 400)
        student = client_for(make_user('someone@thapar.edu'))
        self.assertEqual(student.get(f'{BASE}/feedback/export/').status_code, 403)

    @mock.patch.dict(AdminExportThrottle.THROTTLE_RATES, {'admin_export': '2/hour'})
    def test_throttled(self):
        codes = [self.client.get(f'{BASE}/stats/export/').status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
