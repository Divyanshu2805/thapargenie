"""Shared answers: 7-day public links to one answer."""

from datetime import timedelta
from unittest import mock

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from common.throttles import SharedViewThrottle
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from chat import retention, sharing
from chat.models import Conversation, Message, MessageSource, SharedAnswer


class SharingTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.student = make_user('student@thapar.edu')
        self.client = client_for(self.student)
        self.public = APIClient()
        conversation = Conversation.objects.create(user=self.student, title='Fees')
        self.question = Message.objects.create(conversation=conversation, role='user',
                                               content='What is the hostel fee?')
        self.answer = Message.objects.create(
            conversation=conversation, parent=self.question, role='assistant',
            content='It is Rs 1,20,000 a year [1].', answer_type='answered', grounded=True,
        )
        MessageSource.objects.create(message=self.answer, position=1, title='Fee notice',
                                     url='https://www.thapar.edu/fees', cited=True)
        MessageSource.objects.create(message=self.answer, position=2, title='Stored scan',
                                     url='http://intranet.local/x.pdf')

    def url(self, message=None):
        return f'/api/v1/messages/{(message or self.answer).pk}/share/'

    def shared(self, token):
        return self.public.get(f'/api/v1/shared/{token}/')


class ShareTests(SharingTestCase):
    def test_create_is_idempotent_and_public_view_needs_no_sign_in(self):
        self.assertEqual(self.client.get(self.url()).data, {'share': None})
        created = self.client.post(self.url())
        self.assertEqual(created.status_code, 201)
        token = created.data['token']
        self.assertEqual(len(token), 32)
        again = self.client.post(self.url())
        self.assertEqual((again.status_code, again.data['token']), (200, token))
        self.assertEqual(self.client.get(self.url()).data['share']['token'], token)
        expires = SharedAnswer.objects.get().expires_at
        self.assertAlmostEqual((expires - timezone.now()).total_seconds(), 7 * 86400, delta=60)

        response = self.shared(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(response['Cache-Control'], 'no-store')
        data = response.json()
        self.assertEqual(data['question'], 'What is the hostel fee?')
        self.assertEqual(data['answer'], 'It is Rs 1,20,000 a year [1].')
        self.assertEqual([source['url'] for source in data['sources']],
                         ['https://www.thapar.edu/fees', ''])
        self.assertNotIn('student@thapar.edu', response.content.decode())
        self.assertEqual(AuditEvent.objects.filter(action='share.created').count(), 1)

    def test_snapshot_survives_edits_but_not_chat_deletion(self):
        token = self.client.post(self.url()).data['token']
        Message.objects.filter(pk=self.answer.pk).update(content='Changed later')
        self.assertEqual(self.shared(token).json()['answer'], 'It is Rs 1,20,000 a year [1].')
        self.answer.conversation.delete()
        self.assertEqual(self.shared(token).status_code, 404)

    def test_revoked_expired_and_unknown_links_look_the_same(self):
        token = self.client.post(self.url()).data['token']
        self.assertEqual(self.client.delete(self.url()).status_code, 204)
        self.assertEqual(AuditEvent.objects.filter(action='share.revoked').count(), 1)
        expired = SharedAnswer.objects.create(
            token='e' * 32, user=self.student, message=self.answer, answer='x',
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        for candidate in (token, expired.token, 'x' * 32, 'short', '../../etc'):
            with self.subTest(token=candidate):
                self.assertEqual(self.shared(candidate).status_code, 404)
        # A new link after revoking is a different one.
        self.assertNotEqual(self.client.post(self.url()).data['token'], token)

    def test_only_own_finished_answers(self):
        other = client_for(make_user('other@thapar.edu'))
        self.assertEqual(other.post(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url(self.question)).status_code, 409)
        Message.objects.filter(pk=self.answer.pk).update(status='streaming')
        self.assertEqual(self.client.post(self.url()).status_code, 409)
        self.assertIn(APIClient().post(self.url()).status_code, (401, 403))

    def test_bearer_token_is_ignored_on_the_public_view(self):
        token = self.client.post(self.url()).data['token']
        response = self.public.get(f'/api/v1/shared/{token}/', HTTP_AUTHORIZATION='Bearer junk')
        self.assertEqual(response.status_code, 200)

    @mock.patch.dict(SharedViewThrottle.THROTTLE_RATES, {'shared_view': '2/min'})
    def test_public_view_is_throttled(self):
        token = self.client.post(self.url()).data['token']
        codes = [self.shared(token).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


class ShareRetentionTests(SharingTestCase):
    def test_purges_links_a_month_after_they_end(self):
        now = timezone.now()
        make = lambda token, **fields: SharedAnswer.objects.create(  # noqa: E731
            token=token * 32, user=self.student, message=self.answer, answer='x', **fields)
        make('a', expires_at=now - timedelta(days=31))
        make('b', expires_at=now + timedelta(days=3), revoked_at=now - timedelta(days=31))
        make('c', expires_at=now - timedelta(days=10))
        make('d', expires_at=now + timedelta(days=3))
        self.assertEqual(sharing.purge(now, dry_run=True), 2)
        results = retention.purge(now)
        self.assertEqual(results['shared_links'], 2)
        self.assertEqual(sorted(SharedAnswer.objects.values_list('token', flat=True)),
                         ['c' * 32, 'd' * 32])
