"""Follow-up suggestions on demand."""

from django.utils import timezone
from rag.llm import BadResponse

from chat.models import ChatSettings, Conversation, Message, UsageDaily
from chat.suggestions import clean
from chat.tests.test_chat import ChatTestCase, approved_user, client_for


class SuggestionTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.conversation_ = self.conversation()
        self.answered(self.conversation_)
        self.answer = Message.objects.get(role=Message.Role.ASSISTANT)

    def suggest(self, message=None, client=None):
        message = message or self.answer
        return (client or self.client).post(f'/api/v1/messages/{message.pk}/suggestions/')

    def llm_calls(self):
        return UsageDaily.objects.get(user=self.user).llm_calls

    def test_answers_carry_no_suggestions_until_asked(self):
        messages = self.client.get(
            f'/api/v1/conversations/{self.conversation_.pk}/messages/').data['messages']
        self.assertEqual(messages[-1]['suggestions'], [])

    def test_generates_cleans_saves_and_reuses(self):
        calls_before = self.llm_calls()
        self.fake.queue({'suggestions': [
            'What is the girls hostel fee for 2026-27?', 'boys hostel fee?', 42,
            '  What is the  mess fee?  ', 'What is the mess fee?', 'Is AC hostel extra?',
            'One too many?',
        ]})
        response = self.suggest()
        self.assertEqual(response.status_code, 200, response.data)
        expected = ['What is the girls hostel fee for 2026-27?', 'What is the mess fee?',
                    'Is AC hostel extra?']
        self.assertEqual(response.data, {'suggestions': expected})
        self.assertEqual(self.llm_calls(), calls_before + 1)

        request = self.fake.requests[-1]
        self.assertIn('boys hostel fee?', request.prompt)
        self.assertIn('Hostel fees', request.prompt)  # the cited source title
        self.assertNotIn(self.user.email, request.prompt)

        # Saved: a second click and a reload cost nothing.
        requests_before = len(self.fake.requests)
        self.assertEqual(self.suggest().data, {'suggestions': expected})
        self.assertEqual(len(self.fake.requests), requests_before)
        messages = self.client.get(
            f'/api/v1/conversations/{self.conversation_.pk}/messages/').data['messages']
        self.assertEqual(messages[-1]['suggestions'], expected)

    def test_an_empty_result_is_not_saved(self):
        self.fake.queue({'suggestions': ['', 'boys hostel fee?']})
        self.assertEqual(self.suggest().data, {'suggestions': []})
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.suggestions, [])

    def test_a_failed_call_can_be_retried(self):
        self.fake.queue(BadResponse('garbled'))
        response = self.suggest()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'suggestions_failed')
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.suggestions, [])

        self.fake.queue({'suggestions': ['Is AC hostel extra?']})
        self.assertEqual(self.suggest().data, {'suggestions': ['Is AC hostel extra?']})

    def test_only_complete_answered_or_cached_replies_qualify(self):
        question = Message.objects.get(role=Message.Role.USER)
        response = self.suggest(question)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'suggestions_unavailable')
        for answer_type in (Message.AnswerType.NO_ANSWER, Message.AnswerType.SMALLTALK):
            Message.objects.filter(pk=self.answer.pk).update(answer_type=answer_type)
            self.assertEqual(self.suggest().status_code, 400, answer_type)
        Message.objects.filter(pk=self.answer.pk).update(
            answer_type=Message.AnswerType.ANSWERED, status=Message.Status.STOPPED)
        self.assertEqual(self.suggest().status_code, 400)

        Message.objects.filter(pk=self.answer.pk).update(
            answer_type=Message.AnswerType.CACHED, status=Message.Status.COMPLETE)
        self.fake.queue({'suggestions': ['Is AC hostel extra?']})
        self.assertEqual(self.suggest().status_code, 200)

    def test_another_students_answer_is_not_found(self):
        intruder = client_for(approved_user('other@thapar.edu'))
        self.assertEqual(self.suggest(client=intruder).status_code, 404)
        self.assertFalse(Conversation.objects.filter(user__email='other@thapar.edu').exists())

    def test_maintenance_and_the_global_budget_apply(self):
        ChatSettings.objects.filter(pk=1).update(maintenance_mode=True,
                                                 maintenance_message='Back at 5 pm')
        ChatSettings.forget()
        response = self.suggest()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['message'], 'Back at 5 pm')

        ChatSettings.objects.filter(pk=1).update(maintenance_mode=False)
        ChatSettings.forget()
        UsageDaily.objects.create(user=None, day=timezone.localdate(), llm_calls=10**6)
        response = self.suggest()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'service_busy')

    def test_suggestions_do_not_use_the_daily_question_limit(self):
        questions = UsageDaily.objects.get(user=self.user).questions
        self.fake.queue({'suggestions': ['Is AC hostel extra?']})
        self.suggest()
        self.assertEqual(UsageDaily.objects.get(user=self.user).questions, questions)


class CleanTests(ChatTestCase):
    def test_clean_handles_bad_shapes(self):
        self.assertEqual(clean(None), [])
        self.assertEqual(clean('a question?'), [])
        long = 'word ' * 60
        [text] = clean([long])
        self.assertLessEqual(len(text), 150)
