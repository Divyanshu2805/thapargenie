"""Suggesting a missing session and issue date, and applying reviewed values."""

from datetime import timedelta

from api.models import AuditEvent
from chat.models import UsageDaily
from django.test import SimpleTestCase
from django.utils import timezone
from rag.llm import BadResponse

from knowledge.details import MAX_AI_DOCUMENTS, sessions_in
from knowledge.models import Document, DocumentStatus
from knowledge.tests.test_admin_api import BASE, AdminKnowledgeTestCase


class SessionPatternTests(SimpleTestCase):
    def test_formats_and_only_consecutive_years(self):
        text = 'Fees 2026-27, session 2025–2026, AY 2024/25, range 2019-2023, year 2026'
        self.assertEqual([s for s, _ in sessions_in(text)], ['2026-27', '2025-26', '2024-25'])
        self.assertEqual(sessions_in('1999-00 or 2099-00')[0][0], '2099-00')
        # File-style names run on after the session; digits must not.
        self.assertEqual(sessions_in('Calendar EVEN 2025-26_PhD-1')[0][0], '2025-26')
        self.assertEqual(sessions_in('Ref 12025-26 and 2025-267'), [])

    def test_evidence_drops_table_borders_and_broken_characters(self):
        from knowledge.details import _excerpt
        self.assertEqual(_excerpt('| | ACADEMIC CALENDAR �(ODD SEM 2025-26) | |', '2025-26'),
                         'ACADEMIC CALENDAR (ODD SEM 2025-26)')


class SuggestDetailsTests(AdminKnowledgeTestCase):
    def document(self, title, text, category='notices'):
        document = self.ready_document(title=title, text=text)
        Document.objects.filter(pk=document.pk).update(category=category)
        return document

    def suggest(self, documents, **body):
        response = self.client.post(f'{BASE}/documents/suggest-details/',
                                    {'ids': [str(d.pk) for d in documents], **body},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return {item['title']: item for item in response.data['results']}

    def test_rules_prefer_the_title_then_a_clear_winner_in_the_text(self):
        docs = [
            self.document('Fee structure 2026-27', 'Fees for 2025-26 were lower.'),
            self.document('Hostel notice', 'For the session 2026-27 the rooms are allotted.'),
            self.document('Calendar', 'Session 2025-26. Odd semester 2025-26. See 2024-25.'),
            self.document('Mixed', 'Compare 2024-25 with 2025-26.'),
            self.document('Undated', 'Library opens at 8 am.'),
        ]
        requests_before = len(self.fake.requests)
        results = self.suggest(docs)
        self.assertEqual(len(self.fake.requests), requests_before)  # no AI without asking

        self.assertEqual((results['Fee structure 2026-27']['academic_year'],
                          results['Fee structure 2026-27']['source']), ('2026-27', 'title'))
        self.assertEqual((results['Hostel notice']['academic_year'],
                          results['Hostel notice']['source']), ('2026-27', 'text'))
        self.assertIn('session 2026-27', results['Hostel notice']['evidence'])
        self.assertEqual(results['Calendar']['academic_year'], '2025-26')
        self.assertEqual(results['Mixed']['academic_year'], '')
        self.assertIn('Several sessions', results['Mixed']['evidence'])
        self.assertEqual((results['Undated']['academic_year'], results['Undated']['source']),
                         ('', ''))
        self.assertIsNone(results['Undated']['effective_date'])

    def test_ai_only_for_what_the_rules_missed_and_its_output_is_checked(self):
        known = self.document('Fee structure 2026-27', 'Fees.')
        unknown = self.document('Scholarship notice', 'Apply by 30 September.')
        future = self.document('Exam notice', 'Exams in December.')
        bad = self.document('Old circular', 'Circular text.')
        failing = self.document('Broken', 'Text.')
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.fake.queue(
            {'academic_year': '2026-27', 'effective_date': '2026-08-12',
             'quote': 'Scholarship session 2026-27, dated 12.08.2026'},
            {'academic_year': '', 'effective_date': tomorrow, 'quote': 'x'},
            {'academic_year': '2026-28', 'effective_date': 'soon', 'quote': 'y'},
            BadResponse('garbled'),
        )
        calls_before = UsageDaily.objects.filter(user=self.admin).first()
        results = self.suggest([known, unknown, future, bad, failing], ai=True)

        self.assertEqual(results['Fee structure 2026-27']['source'], 'title')
        self.assertEqual((results['Scholarship notice']['academic_year'],
                          results['Scholarship notice']['effective_date'],
                          results['Scholarship notice']['source']),
                         ('2026-27', '2026-08-12', 'ai'))
        for title in ('Exam notice', 'Old circular', 'Broken'):  # future date, bad year, error
            self.assertEqual((results[title]['academic_year'], results[title]['source']), ('', ''))
        self.assertIsNone(calls_before)
        # Counted like every other call: the three that returned (the client counts
        # successful calls only).
        self.assertEqual(UsageDaily.objects.get(user=self.admin).llm_calls, 3)
        self.assertTrue(AuditEvent.objects.filter(action='document.details_suggested').exists())
        prompt = self.fake.requests[-4].prompt
        self.assertIn('Scholarship notice', prompt)
        self.assertIn('Apply by 30 September.', prompt)

    def test_ai_is_capped_per_request(self):
        docs = [self.document(f'Notice {i}', f'No session in notice {i}.')
                for i in range(MAX_AI_DOCUMENTS + 2)]
        self.suggest(docs, ai=True)
        self.assertEqual(len(self.fake.requests), MAX_AI_DOCUMENTS)

    def test_ai_respects_the_global_budget(self):
        UsageDaily.objects.create(user=None, day=timezone.localdate(), llm_calls=10**6)
        response = self.client.post(f'{BASE}/documents/suggest-details/',
                                    {'ids': [str(self.document('N', 'x').pk)], 'ai': True},
                                    format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'service_busy')

    def test_request_validation(self):
        for body in ({'ids': []}, {'ids': ['nope']}, {'ids': [], 'ai': 'maybe'},
                     {'ids': [str(self.document('N', 'x').pk)], 'extra': 1}):
            response = self.client.post(f'{BASE}/documents/suggest-details/', body,
                                        format='json')
            self.assertEqual(response.status_code, 400, body)

    def test_missing_session_filter(self):
        self.document('Notice without a session', 'x')
        dated = self.document('Notice with a session', 'y')
        Document.objects.filter(pk=dated.pk).update(academic_year='2026-27')
        self.document('Dr. Someone', 'Profile.', category='faculty')
        queued = self.document('Queued notice', 'z')
        Document.objects.filter(pk=queued.pk).update(status=DocumentStatus.QUEUED)
        response = self.client.get(f'{BASE}/documents/', {'details': 'missing_session'})
        self.assertEqual([d['title'] for d in response.data['results']],
                         ['Notice without a session'])
        self.assertEqual(self.client.get(f'{BASE}/documents/', {'details': 'x'}).status_code, 400)


class BulkChangesByIdTests(AdminKnowledgeTestCase):
    def test_each_document_gets_its_own_values(self):
        first = self.ready_document(title='A', text='Alpha text.')
        second = self.ready_document(title='B', text='Beta text.')
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(f'{BASE}/documents/bulk/', {
                'action': 'update', 'ids': [str(first.pk), str(second.pk)],
                'changes_by_id': {
                    str(first.pk): {'academic_year': '2026-27', 'effective_date': '2026-08-01'},
                    str(second.pk): {'academic_year': '2025-26'},
                },
            }, format='json')
        self.assertEqual(response.data['failed'], [])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.academic_year, str(first.effective_date)),
                         ('2026-27', '2026-08-01'))
        self.assertEqual((second.academic_year, second.effective_date), ('2025-26', None))

    def test_validation(self):
        doc = self.ready_document()
        ids = [str(doc.pk)]
        for body in (
            {'action': 'update', 'ids': ids, 'changes': {'is_current': False},
             'changes_by_id': {ids[0]: {'is_current': False}}},
            {'action': 'update', 'ids': ids, 'changes_by_id': {}},
            {'action': 'update', 'ids': ids, 'changes_by_id': {ids[0]: {}}},
            {'action': 'update', 'ids': ids,
             'changes_by_id': {'00000000-0000-0000-0000-000000000000': {'is_current': False}}},
            {'action': 'update', 'ids': ids, 'changes_by_id': {ids[0]: {'title': 'x'}}},
            {'action': 'enable', 'ids': ids, 'changes_by_id': {ids[0]: {'is_current': True}}},
        ):
            response = self.client.post(f'{BASE}/documents/bulk/', body, format='json')
            self.assertEqual(response.status_code, 400, body)
