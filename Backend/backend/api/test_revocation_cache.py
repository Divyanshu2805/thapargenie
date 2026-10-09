import time
from unittest import mock

from common.tests.helpers import make_user
from django.test import SimpleTestCase, TestCase, override_settings
from firebase_admin import auth
from rest_framework.test import APIClient

from api import firebase
from api.firebase import (
    RevokedFirebaseToken,
    recently_verified,
    recently_verified_tokens,
    verify_firebase_id_token,
)
from api.test_identity import _claims, _token


class CacheCase:
    def setUp(self):
        super().setUp()
        recently_verified_tokens.clear()
        self.addCleanup(recently_verified_tokens.clear)
        sdk = mock.patch.object(firebase.auth, 'verify_id_token')
        self.sdk = sdk.start()
        self.addCleanup(sdk.stop)
        app = mock.patch.object(firebase, 'get_firebase_app', return_value=object())
        app.start()
        self.addCleanup(app.stop)


@override_settings(FIREBASE_REVOCATION_CACHE_SECONDS=60)
class RecentlyVerifiedTests(CacheCase, SimpleTestCase):
    def test_a_confirmed_token_is_remembered_for_the_window_only(self):
        self.sdk.return_value = _claims()
        with mock.patch.object(firebase.time, 'monotonic', side_effect=[1000, 1000, 1059, 1061]):
            verify_firebase_id_token('token-a')  # stored at 1000
            self.assertEqual(recently_verified('token-a')['uid'], 'firebase-uid-1')  # at 1000
            self.assertIsNotNone(recently_verified('token-a'))  # 59 s later
            self.assertIsNone(recently_verified('token-a'))  # 61 s later
        self.assertEqual(self.sdk.call_count, 1)

    def test_verifying_always_asks_firebase(self):
        self.sdk.return_value = _claims()
        verify_firebase_id_token('token-a')
        verify_firebase_id_token('token-a')
        self.assertEqual(self.sdk.call_count, 2)
        self.assertTrue(self.sdk.call_args.kwargs['check_revoked'])

    def test_a_failed_check_is_never_remembered(self):
        self.sdk.side_effect = auth.RevokedIdTokenError('revoked')
        with self.assertRaises(RevokedFirebaseToken):
            verify_firebase_id_token('token-a')
        self.assertIsNone(recently_verified('token-a'))

    def test_tokens_are_kept_apart(self):
        self.sdk.return_value = _claims()
        verify_firebase_id_token('token-a')
        self.assertIsNone(recently_verified('token-b'))

    def test_callers_get_copies(self):
        self.sdk.return_value = _claims()
        verify_firebase_id_token('token-a')
        recently_verified('token-a')['uid'] = 'someone-else'
        self.assertEqual(recently_verified('token-a')['uid'], 'firebase-uid-1')

    def test_the_cache_is_bounded_and_drops_the_oldest(self):
        self.sdk.return_value = _claims()
        with mock.patch.object(type(recently_verified_tokens), 'MAX_ENTRIES', 3):
            for name in ('t1', 't2', 't3', 't4'):
                verify_firebase_id_token(name)
        self.assertIsNone(recently_verified('t1'))
        self.assertIsNotNone(recently_verified('t4'))
        self.assertEqual(len(recently_verified_tokens._entries), 3)

    @override_settings(FIREBASE_REVOCATION_CACHE_SECONDS=0)
    def test_a_zero_window_turns_it_off(self):
        self.sdk.return_value = _claims()
        verify_firebase_id_token('token-a')
        self.assertIsNone(recently_verified('token-a'))

    def test_raw_tokens_are_not_kept_in_the_cache(self):
        self.sdk.return_value = _claims()
        verify_firebase_id_token('secret-token-value')
        self.assertNotIn('secret-token-value', repr(recently_verified_tokens._entries))


@override_settings(
    FIREBASE_PROJECT_ID='demo-thapargenie',
    FIREBASE_AUTH_EMULATOR_HOST='',
    FIREBASE_ALLOWED_SIGN_IN_PROVIDERS=('password', 'google.com'),
    FIREBASE_REVOCATION_CACHE_SECONDS=60,
)
class RecentAuthenticationTests(CacheCase, TestCase):
    def setUp(self):
        super().setUp()
        self.token = _token()
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def sign_in_as(self, user):
        self.claims = _claims(uid=user.firebase_uid, sub=user.firebase_uid, email=user.email)
        self.sdk.return_value = self.claims

    def get_me(self):
        return self.client.get('/api/v1/me/')

    def test_a_student_is_checked_with_firebase_once_per_window(self):
        self.sign_in_as(make_user('student@thapar.edu'))
        for _ in range(3):
            self.assertEqual(self.get_me().status_code, 200)
        self.assertEqual(self.sdk.call_count, 1)

    def test_staff_are_checked_with_firebase_on_every_request(self):
        self.sign_in_as(make_user('admin@thapar.edu', staff=True))
        for _ in range(3):
            self.assertEqual(self.get_me().status_code, 200)
        self.assertEqual(self.sdk.call_count, 3)

    def test_staff_revoked_in_firebase_are_cut_off_at_once(self):
        self.sign_in_as(make_user('admin@thapar.edu', staff=True))
        self.assertEqual(self.get_me().status_code, 200)
        self.sdk.side_effect = auth.RevokedIdTokenError('revoked')
        response = self.get_me()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'revoked_identity_token')

    def test_a_student_revoked_in_firebase_loses_access_when_the_window_ends(self):
        self.sign_in_as(make_user('student@thapar.edu'))
        self.assertEqual(self.get_me().status_code, 200)
        self.sdk.side_effect = auth.RevokedIdTokenError('revoked')
        self.assertEqual(self.get_me().status_code, 200)  # still inside the window
        recently_verified_tokens.clear()  # the window passes
        self.assertEqual(self.get_me().status_code, 401)

    def test_sign_out_everywhere_still_applies_at_once(self):
        user = make_user('student@thapar.edu')
        self.sign_in_as(user)
        self.assertEqual(self.get_me().status_code, 200)
        user.firebase_tokens_valid_after = auth_time_plus(self.claims, 5)
        user.save(update_fields=['firebase_tokens_valid_after'])
        response = self.get_me()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'revoked_identity_token')
        self.assertEqual(self.sdk.call_count, 1)  # decided from our own database

    def test_a_suspended_account_is_refused_at_once(self):
        user = make_user('student@thapar.edu')
        self.sign_in_as(user)
        self.assertEqual(self.get_me().status_code, 200)
        user.is_active = False
        user.save(update_fields=['is_active'])
        self.assertEqual(self.get_me().status_code, 401)

    def test_a_remembered_token_cannot_outlive_its_expiry(self):
        user = make_user('student@thapar.edu')
        self.sign_in_as(user)
        expired = {**self.claims, 'exp': int(time.time()) - 600}
        recently_verified_tokens.put(self.token, expired)
        response = self.get_me()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'expired_identity_token')
        self.assertEqual(self.sdk.call_count, 0)


def auth_time_plus(claims, seconds):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(claims['auth_time'] + seconds, tz=timezone.utc)
