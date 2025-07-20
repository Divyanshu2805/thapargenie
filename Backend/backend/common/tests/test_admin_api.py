import uuid
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import get_resolver
from rest_framework.test import APIClient
from userauths.models import EligibilityState

from common.tests.helpers import client_for, make_user
from common.throttles import AdminWriteThrottle

ADMIN_PREFIX = 'api/v1/admin/'


def admin_routes():
    """Every (path, methods) under /api/v1/admin/, with placeholder ids filled in."""
    routes = []
    for entry in get_resolver().url_patterns:
        if str(entry.pattern) != ADMIN_PREFIX:
            continue
        for pattern in entry.url_patterns:
            route = str(pattern.pattern)
            route = route.replace('<int:user_id>', '999999')
            for converter in ('document_id', 'chunk_id', 'feedback_id', 'invitation_id',
                              'notice_id'):
                route = route.replace(f'<uuid:{converter}>', str(uuid.uuid4()))
            view = pattern.callback.view_class
            methods = [m for m in ('get', 'post', 'patch', 'delete') if hasattr(view, m)]
            routes.append((f'/{ADMIN_PREFIX}{route}', methods))
    return routes


class AdminPermissionTests(TestCase):
    def test_every_admin_route_is_covered(self):
        paths = {path.split('/')[4] for path, _ in admin_routes()}
        expected = {'documents'}
        expected |= {'stats', 'gaps', 'feedback', 'settings'}
        expected |= {'playground'}
        self.assertEqual(paths, expected)

    def assert_refused(self, client, expected):
        for path, methods in admin_routes():
            for method in methods:
                response = getattr(client, method)(path, {}, format='json')
                self.assertEqual(response.status_code, expected, f'{method} {path}')

    def test_student_is_refused_everywhere(self):
        self.assert_refused(client_for(make_user('student@thapar.edu')), 403)

    def test_staff_without_approval_is_refused(self):
        staff = make_user('pending-staff@thapar.edu', staff=True,
                          state=EligibilityState.SUSPENDED)
        self.assert_refused(client_for(staff), 403)

    def test_staff_with_unverified_email_is_refused(self):
        staff = make_user('unverified@thapar.edu', staff=True)
        self.assert_refused(client_for(staff, email_verified=False), 403)

    def test_anonymous_is_refused(self):
        self.assert_refused(APIClient(), 401)

    def test_deletes_need_a_recent_sign_in(self):
        staff = make_user('admin@thapar.edu', staff=True)
        client = client_for(staff, signed_in_seconds_ago=3600)
        deletes = [path for path, methods in admin_routes() if 'delete' in methods]
        self.assertEqual(len(deletes), 1)
        for path in deletes:
            response = client.delete(path)
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(response.data['error']['code'], 'recent_auth_required')

    @mock.patch.object(AdminWriteThrottle, 'THROTTLE_RATES', {'admin_write': '2/min'})
    def test_admin_writes_are_throttled_and_reads_are_not(self):
        cache.clear()
        client = client_for(make_user('admin@thapar.edu', staff=True))
        for _ in range(4):
            self.assertEqual(client.get('/api/v1/admin/settings/').status_code, 200)
        codes = [
            client.patch('/api/v1/admin/settings/', {'banner_text': f'b{i}'},
                         format='json').status_code
            for i in range(3)
        ]
        self.assertEqual(codes, [200, 200, 429])
