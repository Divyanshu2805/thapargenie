"""The shared demo account: what it may not do, and the daily reset."""

from unittest import mock

from common.tests.helpers import client_for, make_user
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from userauths.demo import DEMO_QUESTIONS, is_demo
from userauths.models import User

from chat.models import Conversation, Feedback, Message, SiteFeedback, UsageDaily
from chat.tests.test_chat import ANALYSIS, ANSWER, ChatTestCase

ME = '/api/v1/me/'


class DemoLockTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.demo = make_user(settings.DEMO_ACCOUNT_EMAIL)
        self.demo_client = client_for(self.demo)

    def test_only_the_configured_email_is_the_demo(self):
        self.assertTrue(is_demo(self.demo))
        self.assertFalse(is_demo(self.user))
        self.assertFalse(is_demo(None))

    def test_me_says_who_is_the_demo(self):
        self.assertTrue(self.demo_client.get(ME).data['is_demo'])
        self.assertFalse(self.client.get(ME).data['is_demo'])

    def test_the_demo_cannot_change_its_profile(self):
        response = self.demo_client.patch(ME, {'campus': 'Elsewhere'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'demo_account_locked')
        self.assertEqual(self.client.patch(ME, {'campus': 'Patiala'}, format='json').status_code,
                         200)

    def test_the_demo_cannot_sign_everyone_out(self):
        with mock.patch('api.views.revoke_firebase_sessions') as revoke:
            response = self.demo_client.post('/api/v1/me/revoke-sessions/')
        self.assertEqual(response.status_code, 403)
        revoke.assert_not_called()

    def test_the_demo_cannot_delete_all_chats(self):
        Conversation.objects.create(user=self.demo)
        self.assertEqual(self.demo_client.delete('/api/v1/conversations/').status_code, 403)
        self.assertEqual(Conversation.objects.filter(user=self.demo).count(), 1)
        Conversation.objects.create(user=self.user)
        self.assertEqual(self.client.delete('/api/v1/conversations/').status_code, 204)


class SeedDemoTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.questions = DEMO_QUESTIONS[:2]
        patcher = mock.patch('chat.management.commands.seed_demo.DEMO_QUESTIONS', self.questions)
        patcher.start()
        self.addCleanup(patcher.stop)
        # The daily reset never touches Firebase, so the account has to exist already.
        self.demo = make_user(settings.DEMO_ACCOUNT_EMAIL)

    def seed(self):
        for _ in self.questions:
            self.fake.queue(ANALYSIS, ANSWER)
        call_command('seed_demo', '--content-only', verbosity=0)

    def test_it_refuses_to_make_the_account_without_firebase(self):
        User.objects.filter(pk=self.demo.pk).delete()
        with self.assertRaises(CommandError):
            call_command('seed_demo', '--content-only', verbosity=0)

    def test_it_makes_the_demo_a_student_called_aarav_with_sample_chats(self):
        self.seed()
        self.demo.refresh_from_db()
        self.assertEqual((self.demo.first_name, self.demo.last_name), ('Aarav', 'Sharma'))
        self.assertFalse(self.demo.is_staff)
        self.assertEqual(self.demo.profile.program, 'B.E. Computer Engineering')
        asked = list(Message.objects.filter(conversation__user=self.demo, role='user')
                     .order_by('created_at').values_list('content', flat=True))
        self.assertEqual(asked, list(self.questions))
        self.assertEqual(Message.objects.filter(conversation__user=self.demo,
                                                status='complete').count(), 4)

    def test_the_seeding_questions_do_not_use_up_the_allowance(self):
        self.seed()
        usage = UsageDaily.objects.get(user=self.demo, day=timezone.localdate())
        self.assertEqual(usage.questions, 0)
        self.assertGreater(usage.llm_calls, 0)

    def test_a_clean_day_asks_nothing(self):
        self.seed()
        ids = set(Conversation.objects.filter(user=self.demo).values_list('pk', flat=True))
        call_command('seed_demo', '--content-only', verbosity=0)
        self.assertEqual(
            set(Conversation.objects.filter(user=self.demo).values_list('pk', flat=True)), ids)

    def test_a_visitors_changes_are_undone(self):
        self.seed()
        sample = Conversation.objects.filter(user=self.demo).first()
        Conversation.objects.filter(pk=sample.pk).update(is_pinned=True)
        extra = Conversation.objects.create(user=self.demo, title='Mine')
        Feedback.objects.create(message=Message.objects.filter(
            conversation__user=self.demo, role='assistant').last(), user=self.demo, rating=1)
        SiteFeedback.objects.create(user=self.demo, kind='other', message='hello there friend')
        self.seed_again_for_missing()
        self.assertFalse(Conversation.objects.filter(pk=extra.pk).exists())
        self.assertFalse(SiteFeedback.objects.filter(user=self.demo).exists())
        self.assertFalse(Feedback.objects.filter(user=self.demo).exists())
        self.assertFalse(Conversation.objects.filter(user=self.demo, is_pinned=True).exists())
        self.assertEqual(Conversation.objects.filter(user=self.demo).count(), 2)

    def seed_again_for_missing(self):
        # The pinned and the rated samples count as changed, so both are asked again.
        for _ in self.questions:
            self.fake.queue(ANALYSIS, ANSWER)
        call_command('seed_demo', '--content-only', verbosity=0)

    def test_other_students_are_left_alone(self):
        mine = Conversation.objects.create(user=self.user)
        self.seed()
        self.assertTrue(Conversation.objects.filter(pk=mine.pk).exists())
