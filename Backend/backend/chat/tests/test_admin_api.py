import json

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from django.test import TestCase
from django.utils import timezone
from rag.llm import LLMError, use_provider
from rag.llm.fake import FakeProvider

from chat.admin_services import pseudonym
from chat.models import (
    AnswerTrace,
    ChatSettings,
    Conversation,
    Feedback,
    Message,
    MessageSource,
    UsageDaily,
)
from chat.tests.test_chat import ANALYSIS, ANSWER, add_document

BASE = '/api/v1/admin'


class AdminChatTestCase(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        use_provider(self.fake)
        self.addCleanup(use_provider, None)
        ChatSettings.forget()
        self.addCleanup(ChatSettings.forget)
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.client = client_for(self.admin)
        self.student = make_user('student.name@thapar.edu')

    def turn(self, question, *, answer=ANSWER, answer_type='answered', standalone=None,
             user=None, latency_ms=1000):
        conversation = Conversation.objects.create(user=user or self.student)
        asked = Message.objects.create(conversation=conversation, role='user', content=question)
        reply = Message.objects.create(
            conversation=conversation, parent=asked, role='assistant', content=answer,
            answer_type=answer_type, grounded=answer_type == 'answered', latency_ms=latency_ms,
        )
        AnswerTrace.objects.create(message=reply, standalone_query=standalone or question,
                                   analysis={'intent': 'college_query'}, retrieval={},
                                   timings={'total': latency_ms})
        return reply


class StatsTests(AdminChatTestCase):
    def test_empty_database(self):
        response = self.client.get(f'{BASE}/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['range_days'], 7)
        self.assertEqual(len(data['daily']), 7)
        self.assertEqual(data['totals']['questions'], 0)
        self.assertIsNone(data['cache_hit_rate'])
        self.assertEqual(data['latency']['p50_ms'], None)
        self.assertEqual(data['answer_types'], {})
        self.assertEqual(data['feedback'], {'up': 0, 'down': 0, 'open_reviews': 0})
        self.assertGreater(data['database_bytes'], 0)
        self.assertEqual(data['knowledge']['chunks'], 0)

    def test_counts_and_latency(self):
        UsageDaily.objects.create(user=self.student, day=timezone.localdate(), questions=4,
                                  answers=4, cached=1, llm_calls=9)
        for latency in (1000, 2000, 3000):
            self.turn('q', latency_ms=latency)
        cached = self.turn('q', answer_type='cached', latency_ms=100)
        self.turn('unknown', answer='I could not find it.', answer_type='no_answer')
        Feedback.objects.create(message=cached, user=self.student, rating=-1)
        add_document('Hostel fees', 'Boys hostel fee is Rs 1,20,000 per year.')

        data = self.client.get(f'{BASE}/stats/', {'range': '30d'}).data
        self.assertEqual(len(data['daily']), 30)
        self.assertEqual(data['daily'][-1]['questions'], 4)
        self.assertEqual(data['totals']['llm_calls'], 9)
        self.assertEqual(data['cache_hit_rate'], 0.25)
        self.assertEqual(data['answer_types'], {'answered': 3, 'cached': 1, 'no_answer': 1})
        self.assertEqual(data['latency']['uncached_p50_ms'], 1500)
        self.assertEqual(data['feedback'], {'up': 0, 'down': 1, 'open_reviews': 1})
        self.assertEqual(data['knowledge']['documents_by_status'], {'ready': 1})
        self.assertEqual(data['knowledge']['searchable_chunks'], 1)
        self.assertEqual(data['budget']['llm_calls_today'], 9)

    def test_invalid_range(self):
        self.assertEqual(self.client.get(f'{BASE}/stats/', {'range': '1y'}).status_code, 400)


class FeedbackTests(AdminChatTestCase):
    def setUp(self):
        super().setUp()
        document = add_document('Hostel fees', 'Boys hostel fee is Rs 1,20,000 per year.')
        self.reply = self.turn('boys hostel fee?')
        MessageSource.objects.create(message=self.reply, position=1, document=document,
                                     title='Hostel fees', cited=True, score=0.8)
        self.feedback = Feedback.objects.create(message=self.reply, user=self.student,
                                                rating=-1, reason='outdated',
                                                comment='This is last year')

    def test_list_shows_the_pair_without_identity(self):
        response = self.client.get(f'{BASE}/feedback/', {'rating': -1,
                                                         'review_status': 'open'})
        self.assertEqual(response.status_code, 200)
        [item] = response.data['results']
        self.assertEqual(item['question'], 'boys hostel fee?')
        self.assertEqual(item['answer']['content'], ANSWER)
        self.assertEqual(item['answer']['sources'][0]['title'], 'Hostel fees')
        self.assertEqual(item['trace']['standalone_query'], 'boys hostel fee?')
        self.assertEqual(item['reporter'], pseudonym(self.student.pk))

        raw = json.dumps(response.data, default=str)
        for secret in (self.student.email, 'student.name', str(self.reply.conversation_id),
                       str(self.reply.pk), self.student.firebase_uid):
            self.assertNotIn(secret, raw)
        self.assertNotIn('user', item)
        self.assertNotIn('conversation_id', raw)

    def test_filters(self):
        for params, expected in (({'rating': 1}, 0), ({'answer_type': 'answered'}, 1),
                                 ({'review_status': 'resolved'}, 0), ({'reason': 'outdated'}, 1)):
            response = self.client.get(f'{BASE}/feedback/', params)
            self.assertEqual(len(response.data['results']), expected, params)
        for name in ('rating', 'review_status', 'answer_type', 'reason'):
            response = self.client.get(f'{BASE}/feedback/', {name: 'nope'})
            self.assertEqual(response.status_code, 400, name)
            self.assertIn(name, response.data['error']['fields'])
        self.assertEqual(self.client.get(f'{BASE}/feedback/', {'rating': 5}).status_code, 400)

    def test_review_is_saved_and_audited(self):
        response = self.client.patch(f'{BASE}/feedback/{self.feedback.pk}/', {
            'review_status': 'resolved', 'admin_note': 'Added the 2026-27 fee sheet.',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['review_status'], 'resolved')
        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.reviewed_by, self.admin)
        self.assertIsNotNone(self.feedback.reviewed_at)
        event = AuditEvent.objects.get(action='feedback.reviewed')
        self.assertEqual(event.metadata['review_status'], 'resolved')
        self.assertNotIn('2026-27 fee sheet', json.dumps(event.metadata))

    def test_review_validation(self):
        url = f'{BASE}/feedback/{self.feedback.pk}/'
        self.assertEqual(self.client.patch(url, {}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'review_status': 'x'},
                                           format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'rating': 1}, format='json').status_code, 400)


class GapTests(AdminChatTestCase):
    def test_unanswered_questions_are_grouped_without_identity(self):
        other = make_user('other@thapar.edu')
        self.turn('Swimming pool timings?', answer_type='no_answer',
                  standalone='swimming pool timings')
        self.turn('when is the pool open', answer_type='no_answer',
                  standalone='Swimming  pool timings', user=other)
        self.turn('bus fee?', answer_type='no_answer', standalone='bus fee')
        self.turn('hostel fee?')

        response = self.client.get(f'{BASE}/gaps/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['range_days'], 30)
        results = response.data['results']
        self.assertEqual([(r['query'], r['count'], r['askers']) for r in results],
                         [('swimming pool timings', 2, 2), ('bus fee', 1, 1)])
        raw = json.dumps(response.data, default=str)
        self.assertNotIn('thapar.edu', raw)
        self.assertNotIn('when is the pool open', raw)


class SettingsTests(AdminChatTestCase):
    def test_get_and_patch(self):
        response = self.client.get(f'{BASE}/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['rerank_enabled'])

        response = self.client.patch(f'{BASE}/settings/', {
            'rerank_enabled': True, 'daily_question_limit': 60,
            'banner_text': '  Fee   deadline  soon ',
            'starter_questions': [{'category': 'Fees', 'text': 'BE fee?'}],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['banner_text'], 'Fee deadline soon')
        settings = ChatSettings.load()
        self.assertTrue(settings.rerank_enabled)
        self.assertEqual(settings.daily_question_limit, 60)
        self.assertEqual(settings.updated_by, self.admin)
        event = AuditEvent.objects.get(action='settings.updated')
        self.assertEqual(event.metadata['values'], {'daily_question_limit': [40, 60],
                                                    'rerank_enabled': [False, True]})
        self.assertIn('banner_text', event.metadata['fields'])
        self.assertNotIn('banner_text', event.metadata['values'])

    def test_no_change_writes_no_audit(self):
        self.client.patch(f'{BASE}/settings/', {'cache_enabled': True}, format='json')
        self.assertFalse(AuditEvent.objects.filter(action='settings.updated').exists())

    def test_validation(self):
        for body in (
            {'daily_question_limit': 0},
            {'global_daily_llm_calls': 10},
            {'banner_text': 'x' * 301},
            {'starter_questions': [{'category': 'a'}]},
            {'starter_questions': [{'category': 'a', 'text': 'b'}] * 9},
            {'maintenance_mode': True},
            {'updated_by': 1},
        ):
            response = self.client.patch(f'{BASE}/settings/', body, format='json')
            self.assertEqual(response.status_code, 400, body)
        response = self.client.patch(f'{BASE}/settings/', {
            'maintenance_mode': True, 'maintenance_message': 'Back at 6 pm.',
        }, format='json')
        self.assertEqual(response.status_code, 200)


class PlaygroundTests(AdminChatTestCase):
    def test_runs_the_pipeline_and_saves_nothing(self):
        document = add_document('Hostel fees', 'Boys hostel fee is Rs 1,20,000 per year.')
        self.fake.queue(ANALYSIS, ANSWER)
        response = self.client.post(f'{BASE}/playground/', {'query': 'boys hostel fee?'},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data['answer'], ANSWER)
        self.assertEqual(data['answer_type'], 'answered')
        self.assertEqual(data['analysis']['standalone_query'], 'boys hostel fee 2026-27')
        self.assertTrue(data['retrieval']['candidates'])
        self.assertIn('fused', data['retrieval']['candidates'][0])
        # Audited by size only: the query text never reaches the audit log.
        event = AuditEvent.objects.get(action='playground.ran')
        self.assertEqual(event.metadata['query_chars'], len('boys hostel fee?'))
        self.assertNotIn('hostel', json.dumps(event.metadata))
        [source] = data['sources']
        self.assertEqual(source['document_id'], str(document.pk))
        self.assertTrue(source['cited'])
        self.assertIn('Rs 1,20,000', source['content'])
        self.assertIn('total', data['timings'])
        self.assertGreater(data['usage']['llm_calls'], 0)

        self.assertFalse(Message.objects.exists())
        self.assertFalse(Conversation.objects.exists())
        usage = UsageDaily.objects.get(user=self.admin)
        self.assertEqual((usage.questions, usage.answers), (0, 0))
        self.assertEqual(usage.llm_calls, data['usage']['llm_calls'])

    def test_history_is_used_and_validated(self):
        self.fake.queue(ANALYSIS, ANSWER)
        response = self.client.post(f'{BASE}/playground/', {
            'query': 'and for girls?',
            'history': [{'role': 'user', 'content': 'boys hostel fee?'},
                        {'role': 'assistant', 'content': ANSWER}],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('boys hostel fee?', str(self.fake.requests[0].prompt))
        bad = self.client.post(f'{BASE}/playground/', {
            'query': 'x', 'history': [{'role': 'system', 'content': 'y'}]}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_llm_failure(self):
        add_document('Hostel fees', 'Boys hostel fee is Rs 1,20,000 per year.')
        self.fake.queue(ANALYSIS, LLMError('down'))
        response = self.client.post(f'{BASE}/playground/', {'query': 'fee?'}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')
