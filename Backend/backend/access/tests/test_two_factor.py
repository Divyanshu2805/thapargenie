"""Staff two-factor: enrolment, the check on the admin API, backup codes and lockout."""

import base64
import time
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from access import two_factor
from access.models import SecondFactor, SecondFactorSession

BASE = '/api/v1/admin'
URL = f'{BASE}/two-factor/'


def code_for(secret, offset=0):
    # two_factor.time is frozen in TwoFactorTests, so both sides agree on the time step.
    return two_factor.totp(secret, int(two_factor.time.time() // two_factor.PERIOD) + offset)


class TotpTests(TestCase):
    def test_matches_the_rfc_6238_test_vectors(self):
        # RFC 6238 appendix B (SHA-1, secret "12345678901234567890"), last six digits.
        secret = base64.b32encode(b'12345678901234567890').decode()
        for seconds, expected in ((59, '287082'), (1111111109, '081804'),
                                  (1234567890, '005924'), (2000000000, '279037')):
            self.assertEqual(two_factor.totp(secret, seconds // 30), expected)

    def test_the_setup_link_names_the_app_and_the_account(self):
        uri = two_factor.provisioning_uri('admin@thapar.edu', 'ABC')
        self.assertTrue(uri.startswith('otpauth://totp/ThaparGenie%3Aadmin%40thapar.edu?'))
        self.assertIn('secret=ABC', uri)
        self.assertIn('issuer=ThaparGenie', uri)


@override_settings(STAFF_TWO_FACTOR_REQUIRED=True)
class TwoFactorTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.client = client_for(self.admin)
        # Codes change every 30 seconds: hold the clock still, or a test that straddles
        # a boundary sees a different code than it computed.
        now = time.time()
        clock = mock.patch.object(two_factor, 'time', SimpleNamespace(time=lambda: now))
        clock.start()
        self.addCleanup(clock.stop)

    def enrol(self, client=None):
        client = client or self.client
        secret = client.post(f'{URL}setup/').data['secret']
        response = client.post(f'{URL}confirm/', {'code': code_for(secret)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return secret, response.data['recovery_codes']

    def test_the_admin_api_is_closed_until_two_factor_is_set_up(self):
        response = self.client.get(f'{BASE}/users/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'second_factor_setup_required')
        self.assertEqual(self.client.get(URL).data, {
            'required': True, 'enrolled': False, 'verified': False,
            'recovery_codes_left': 0, 'session_hours': 12,
        })

    def test_every_other_admin_route_asks_for_the_second_step(self):
        from common.tests.test_admin_api import admin_routes

        checked = 0
        for path, methods in admin_routes():
            if '/two-factor/' in path:
                continue
            for method in methods:
                response = getattr(self.client, method)(path, {}, format='json')
                self.assertEqual(response.status_code, 403, f'{method} {path}')
                self.assertEqual(response.data['error']['code'], 'second_factor_setup_required',
                                 f'{method} {path}')
                checked += 1
        self.assertGreater(checked, 30)

    def test_enrolling_opens_the_admin_api_for_this_sign_in(self):
        secret, codes = self.enrol()
        self.assertEqual(len(codes), two_factor.RECOVERY_CODES)
        self.assertEqual(len(set(codes)), len(codes))
        self.assertEqual(self.client.get(f'{BASE}/users/').status_code, 200)
        status = self.client.get(URL).data
        self.assertEqual((status['enrolled'], status['verified'], status['recovery_codes_left']),
                         (True, True, 10))
        factor = SecondFactor.objects.get(user=self.admin)
        # Neither the key nor the backup codes are stored readable.
        self.assertNotIn(secret, factor.secret)
        self.assertFalse(set(codes) & set(factor.recovery_codes))
        self.assertTrue(AuditEvent.objects.filter(action='second_factor.enrolled',
                                                  actor=self.admin).exists())

    def test_a_wrong_code_does_not_enrol(self):
        self.client.post(f'{URL}setup/')
        response = self.client.post(f'{URL}confirm/', {'code': '000000'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'second_factor_invalid_code')
        self.assertEqual(self.client.get(f'{BASE}/users/').status_code, 403)

    def test_a_new_sign_in_needs_the_code_again(self):
        secret, _ = self.enrol()
        later = client_for(self.admin, signed_in_seconds_ago=5)  # another sign-in
        response = later.get(f'{BASE}/users/')
        self.assertEqual(response.data['error']['code'], 'second_factor_required')
        # The code that enrolled cannot be replayed; the next one works.
        replay = later.post(f'{URL}verify/', {'code': code_for(secret)}, format='json')
        self.assertEqual(replay.status_code, 400)
        response = later.post(f'{URL}verify/', {'code': code_for(secret, 1)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['verified'])
        self.assertEqual(later.get(f'{BASE}/users/').status_code, 200)

    def test_the_check_expires(self):
        self.enrol()
        SecondFactorSession.objects.update(verified_at=timezone.now() - timedelta(hours=13))
        response = self.client.get(f'{BASE}/users/')
        self.assertEqual(response.data['error']['code'], 'second_factor_required')

    def test_a_backup_code_works_once(self):
        _, codes = self.enrol()
        later = client_for(self.admin, signed_in_seconds_ago=5)
        body = {'recovery_code': codes[0].lower().replace('-', ' ')}
        response = later.post(f'{URL}verify/', body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['recovery_codes_left'], 9)
        event = AuditEvent.objects.get(action='second_factor.recovery_code_used')
        self.assertEqual(event.metadata, {'left': 9})
        again = client_for(self.admin, signed_in_seconds_ago=9)
        self.assertEqual(again.post(f'{URL}verify/', body, format='json').status_code, 400)

    def test_five_wrong_codes_lock_it_for_a_while(self):
        secret, _ = self.enrol()
        later = client_for(self.admin, signed_in_seconds_ago=5)
        for _ in range(two_factor.MAX_FAILED_ATTEMPTS):
            response = later.post(f'{URL}verify/', {'code': '000000'}, format='json')
            self.assertEqual(response.status_code, 400)
        response = later.post(f'{URL}verify/', {'code': code_for(secret, 1)}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['error']['code'], 'second_factor_locked')
        self.assertTrue(AuditEvent.objects.filter(action='second_factor.locked').exists())
        SecondFactor.objects.update(locked_until=timezone.now() - timedelta(seconds=1))
        response = later.post(f'{URL}verify/', {'code': code_for(secret, 1)}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_setup_cannot_replace_a_working_factor(self):
        self.enrol()
        response = self.client.post(f'{URL}setup/')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'second_factor_already_set_up')

    def test_new_backup_codes_replace_the_old_ones(self):
        _, old = self.enrol()
        response = self.client.post(f'{URL}recovery-codes/')
        self.assertEqual(response.status_code, 200, response.data)
        new = response.data['recovery_codes']
        self.assertFalse(set(old) & set(new))
        later = client_for(self.admin, signed_in_seconds_ago=5)
        self.assertEqual(later.post(f'{URL}verify/', {'recovery_code': old[0]},
                                    format='json').status_code, 400)
        self.assertEqual(later.post(f'{URL}verify/', {'recovery_code': new[0]},
                                    format='json').status_code, 200)

    def test_new_backup_codes_need_the_second_step_and_a_recent_sign_in(self):
        self.enrol()
        unverified = client_for(self.admin, signed_in_seconds_ago=5)
        self.assertEqual(unverified.post(f'{URL}recovery-codes/').status_code, 403)
        old = client_for(self.admin, signed_in_seconds_ago=3600)
        two_factor._start_session(self.admin, old.handler._force_token.auth_time)
        response = old.post(f'{URL}recovery-codes/')
        self.assertEqual(response.data['error']['code'], 'recent_auth_required')

    def test_validation(self):
        self.enrol()
        for body in ({}, {'code': '12345'}, {'code': 'abcdef'}, {'recovery_code': 'short'},
                     {'code': '123456', 'recovery_code': 'ABCD-EFGH'}, {'code': '123456', 'x': 1}):
            with self.subTest(body=body):
                response = self.client.post(f'{URL}verify/', body, format='json')
                self.assertEqual(response.status_code, 400)

    def test_students_cannot_reach_it(self):
        student = client_for(make_user('student@thapar.edu'))
        for method, path in (('get', URL), ('post', f'{URL}setup/'), ('post', f'{URL}verify/')):
            self.assertEqual(getattr(student, method)(path).status_code, 403)
        self.assertFalse(SecondFactor.objects.exists())

    def test_one_admins_factor_does_not_open_the_door_for_another(self):
        self.enrol()
        other = client_for(make_user('other@thapar.edu', staff=True))
        response = other.get(f'{BASE}/users/')
        self.assertEqual(response.data['error']['code'], 'second_factor_setup_required')

    def test_student_pages_do_not_ask_staff_for_a_code(self):
        self.assertEqual(self.client.get('/api/v1/conversations/').status_code, 200)

    def test_reset_command_makes_them_enrol_again(self):
        self.enrol()
        out = StringIO()
        call_command('reset_second_factor', '--email', 'Admin@Thapar.edu', '--reason',
                     'lost phone', stdout=out)
        self.assertIn('Two-factor reset', out.getvalue())
        self.assertFalse(SecondFactor.objects.exists())
        self.assertFalse(SecondFactorSession.objects.exists())
        event = AuditEvent.objects.get(action='second_factor.reset')
        self.assertEqual((event.actor, event.metadata), (None, {'reason': 'lost phone'}))
        response = self.client.get(f'{BASE}/users/')
        self.assertEqual(response.data['error']['code'], 'second_factor_setup_required')
        with self.assertRaises(CommandError):
            call_command('reset_second_factor', '--email', 'nobody@thapar.edu', '--reason', 'x')

    @override_settings(SECRET_KEY='a-different-key-' + 'y' * 60)
    def test_a_changed_secret_key_asks_for_a_reset_instead_of_crashing(self):
        with override_settings(SECRET_KEY='the-original-key-' + 'x' * 60):
            secret, _ = self.enrol()
        later = client_for(self.admin, signed_in_seconds_ago=5)
        response = later.post(f'{URL}verify/', {'code': code_for(secret, 1)}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'second_factor_reset_required')


class TwoFactorOffTests(TestCase):
    def test_switched_off_the_admin_api_is_as_before(self):
        admin = client_for(make_user('admin@thapar.edu', staff=True))
        self.assertEqual(admin.get(f'{BASE}/users/').status_code, 200)
        self.assertFalse(admin.get(URL).data['required'])

    def test_it_is_on_unless_switched_off(self):
        from backend.settings import base

        self.assertTrue(base.STAFF_TWO_FACTOR_REQUIRED)
