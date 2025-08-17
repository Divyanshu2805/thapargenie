"""Site feedback: students send it, admins review it."""

from datetime import timedelta
from unittest import mock

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from common.throttles import SiteFeedbackThrottle
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from chat import retention
from chat.admin_services import pseudonym
from chat.models import SiteFeedback

URL = '/api/v1/site-feedback/'
ADMIN_URL = '/api/v1/admin/site-feedback/'
VALID = {'kind': 'suggestion', 'rating': 4, 'message': 'A dark mode for the PDF viewer, please.',
         'page': '/chat/', 'contact_ok': False}


class StudentSiteFeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = make_user('student@thapar.edu')
        self.client = client_for(self.student)

    def test_create_and_list_own(self):
        response = self.client.post(URL, VALID, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['review_status'], 'open')
        item = SiteFeedback.objects.get()
        self.assertEqual((item.user, item.kind, item.rating, item.page),
                         (self.student, 'suggestion', 4, '/chat/'))

        other = make_user('other@thapar.edu')
        SiteFeedback.objects.create(user=other, kind='problem', message='Someone else wrote this.')
        listed = self.client.get(URL).data['results']
        self.assertEqual([entry['id'] for entry in listed], [str(item.pk)])
        self.assertNotIn('admin_note', listed[0])

    def test_message_is_trimmed_and_needs_ten_characters(self):
        response = self.client.post(URL, {**VALID, 'message': '   too short  '}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(URL, {**VALID, 'message': '  long enough now  '}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SiteFeedback.objects.get().message, 'long enough now')

    def test_rejects_bad_input(self):
        for changes in ({'rating': 6}, {'rating': 0}, {'kind': 'praise'},
                        {'page': 'https://evil.example/'}, {'extra': 'field'}):
            with self.subTest(changes=changes):
                response = self.client.post(URL, {**VALID, **changes}, format='json')
                self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteFeedback.objects.exists())

    def test_rating_is_optional(self):
        body = {key: value for key, value in VALID.items() if key != 'rating'}
        self.assertEqual(self.client.post(URL, body, format='json').status_code, 201)
        self.assertIsNone(SiteFeedback.objects.get().rating)

    def test_needs_sign_in(self):
        self.assertIn(APIClient().post(URL, VALID, format='json').status_code, (401, 403))

    @mock.patch.dict(SiteFeedbackThrottle.THROTTLE_RATES, {'site_feedback': '2/hour'})
    def test_throttled(self):
        codes = [self.client.post(URL, VALID, format='json').status_code for _ in range(3)]
        self.assertEqual(codes, [201, 201, 429])
        # Reading your own feedback is not limited.
        self.assertEqual(self.client.get(URL).status_code, 200)


class AdminSiteFeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.client = client_for(self.admin)
        self.student = make_user('student@thapar.edu')

    def test_list_is_pseudonymous_unless_contact_allowed(self):
        quiet = SiteFeedback.objects.create(user=self.student, kind='problem',
                                            message='The sidebar flickers on my phone.')
        open_to_contact = SiteFeedback.objects.create(
            user=self.student, kind='suggestion', message='Add hostel mess menus.',
            contact_ok=True,
        )
        results = {item['id']: item for item in self.client.get(ADMIN_URL).data['results']}
        self.assertEqual(results[str(quiet.pk)]['reporter'], pseudonym(self.student.pk))
        self.assertIsNone(results[str(quiet.pk)]['contact_email'])
        self.assertEqual(results[str(open_to_contact.pk)]['contact_email'], 'student@thapar.edu')

    def test_filters(self):
        SiteFeedback.objects.create(user=self.student, kind='problem', message='Broken thing here.')
        SiteFeedback.objects.create(user=self.student, kind='suggestion',
                                    message='An idea for you.', review_status='resolved')
        problems = self.client.get(f'{ADMIN_URL}?kind=problem').data['results']
        self.assertEqual([item['kind'] for item in problems], ['problem'])
        resolved = self.client.get(f'{ADMIN_URL}?review_status=resolved').data['results']
        self.assertEqual([item['kind'] for item in resolved], ['suggestion'])
        self.assertEqual(self.client.get(f'{ADMIN_URL}?kind=nope').status_code, 400)

    def test_review_is_audited(self):
        item = SiteFeedback.objects.create(user=self.student, kind='answers',
                                           message='Fee answers were out of date.')
        response = self.client.patch(f'{ADMIN_URL}{item.pk}/',
                                     {'review_status': 'resolved', 'admin_note': 'Fees updated.'},
                                     format='json')
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.review_status, item.admin_note, item.reviewed_by),
                         ('resolved', 'Fees updated.', self.admin))
        self.assertTrue(AuditEvent.objects.filter(action='site_feedback.reviewed').exists())
        # The student sees the new status, never the note.
        mine = client_for(self.student).get(URL).data['results'][0]
        self.assertEqual(mine['review_status'], 'resolved')
        self.assertNotIn('admin_note', mine)

    def test_students_cannot_use_the_admin_endpoints(self):
        student = client_for(self.student)
        self.assertEqual(student.get(ADMIN_URL).status_code, 403)


class SiteFeedbackRetentionTests(TestCase):
    def test_old_feedback_is_purged(self):
        student = make_user('student@thapar.edu')
        old = SiteFeedback.objects.create(user=student, kind='other', message='From a year ago.')
        a_year_ago = timezone.now() - timedelta(days=400)
        SiteFeedback.objects.filter(pk=old.pk).update(created_at=a_year_ago)
        fresh = SiteFeedback.objects.create(user=student, kind='other', message='From this week.')
        self.assertEqual(retention.purge()['site_feedback'], 1)
        self.assertEqual(list(SiteFeedback.objects.values_list('pk', flat=True)), [fresh.pk])
