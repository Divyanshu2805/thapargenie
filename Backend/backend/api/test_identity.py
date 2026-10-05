import base64
import json
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone as django_timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from userauths.models import EligibilityState, IdentityInvitation, User

from api.firebase import (
    DisabledFirebaseUser,
    InvalidFirebaseToken,
    RevokedFirebaseToken,
)
from api.identity import FirebaseIdentity, resolve_local_identity
from api.models import AuditEvent
from api.permissions import HasVerifiedEligibleIdentity


def _segment(value):
    raw = json.dumps(value, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def _token(header=None):
    header = header or {'alg': 'RS256', 'kid': 'synthetic-key', 'typ': 'JWT'}
    return f'{_segment(header)}.{_segment({"test": True})}.synthetic-signature'


def _claims(**overrides):
    now = int(time.time())
    claims = {
        'aud': 'demo-thapargenie',
        'iss': 'https://securetoken.google.com/demo-thapargenie',
        'sub': 'firebase-uid-1',
        'uid': 'firebase-uid-1',
        'email': 'student@example.com',
        'email_verified': True,
        'iat': now - 30,
        'exp': now + 3300,
        'auth_time': now - 30,
        'firebase': {'sign_in_provider': 'password'},
        'given_name': 'Synthetic',
        'family_name': 'Student',
    }
    claims.update(overrides)
    return claims


@override_settings(
    FIREBASE_PROJECT_ID='demo-thapargenie',
    FIREBASE_AUTH_EMULATOR_HOST='',
    FIREBASE_ALLOWED_SIGN_IN_PROVIDERS=('password', 'google.com'),
)
class FirebaseAuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.token = _token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_missing_token_is_rejected(self):
        response = APIClient().get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'not_authenticated')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_valid_unverified_token_creates_one_pending_identity(self, verify):
        verify.return_value = _claims(email_verified=False)

        first = self.client.get('/api/v1/me/')
        second = self.client.get('/api/v1/me/')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(User.objects.filter(firebase_uid='firebase-uid-1').count(), 1)
        self.assertEqual(first.json()['onboarding_status'], 'email_verification_required')
        user = User.objects.get(firebase_uid='firebase-uid-1')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.eligibility_state, EligibilityState.PENDING)

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_only_approved_students_can_edit_preferences(self, verify):
        body = {'program': 'BEng'}
        verify.return_value = _claims(email_verified=False)
        unverified = self.client.patch('/api/v1/me/', body, format='json')
        verify.return_value = _claims()
        pending = self.client.patch('/api/v1/me/', body, format='json')

        self.assertEqual(unverified.status_code, 403)
        self.assertEqual(unverified.json()['error']['code'], 'email_verification_required')
        self.assertEqual(pending.status_code, 403)
        self.assertEqual(pending.json()['error']['code'], 'eligibility_required')
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)  # status stays readable
        self.assertEqual(User.objects.get(firebase_uid='firebase-uid-1').profile.program, '')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_verified_invited_identity_is_approved_and_me_is_allowlisted(self, verify):
        IdentityInvitation.objects.create(email='STUDENT@example.com')
        verify.return_value = _claims()

        response = self.client.patch(
            '/api/v1/me/',
            {'campus': 'Main', 'program': 'BEng', 'academic_year': 2},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['onboarding_status'], 'ready')
        self.assertEqual(payload['eligibility_state'], EligibilityState.APPROVED)
        self.assertIs(payload['is_staff'], False)
        self.assertEqual(payload['preferences']['program'], 'BEng')
        invitation = IdentityInvitation.objects.get()
        self.assertFalse(invitation.is_active)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertTrue(AuditEvent.objects.filter(action='eligibility.invitation_accepted').exists())

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_expired_token_is_rejected(self, verify):
        now = int(time.time())
        verify.return_value = _claims(exp=now - settings.FIREBASE_CLOCK_SKEW_SECONDS - 1)

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'expired_identity_token')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_wrong_project_token_is_rejected(self, verify):
        verify.return_value = _claims(aud='another-project')

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'invalid_identity_token')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_forged_token_is_rejected(self, verify):
        verify.side_effect = InvalidFirebaseToken('signature mismatch')

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertNotIn('signature mismatch', response.content.decode())

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_revoked_token_is_rejected(self, verify):
        verify.side_effect = RevokedFirebaseToken('revoked')

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'revoked_identity_token')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_disabled_firebase_user_is_rejected(self, verify):
        verify.side_effect = DisabledFirebaseUser('disabled')

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'disabled_identity')

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_unsigned_token_is_rejected_outside_emulator(self, verify):
        verify.return_value = _claims()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token({"alg": "none"})}')

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_legacy_email_match_is_not_automatically_linked(self, verify):
        legacy = User.objects.create_user(email='student@example.com')
        verify.return_value = _claims()

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 403)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.firebase_uid)
        self.assertEqual(User.objects.count(), 1)

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_client_cannot_assign_staff_or_eligibility(self, verify):
        # An approved student may edit preferences, but still not these fields.
        IdentityInvitation.objects.create(email='student@example.com')
        verify.return_value = _claims()

        response = self.client.patch(
            '/api/v1/me/',
            {'is_staff': True, 'eligibility_state': 'approved'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        user = User.objects.get(firebase_uid='firebase-uid-1')
        self.assertFalse(user.is_staff)
        self.assertEqual(user.eligibility_state, EligibilityState.APPROVED)  # via the invitation

    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_backend_revocation_watermark_rejects_older_token(self, verify):
        claims = _claims()
        user = User.objects.create_user(
            email=claims['email'],
            firebase_uid=claims['uid'],
            firebase_tokens_valid_after=datetime.fromtimestamp(
                claims['auth_time'] + 1,
                tz=timezone.utc,
            ),
        )
        verify.return_value = claims

        response = self.client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'revoked_identity_token')
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.firebase_uid, claims['uid'])

    @mock.patch('api.views.revoke_firebase_sessions')
    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_recent_identity_can_revoke_sessions(self, verify, revoke):
        verify.return_value = _claims()
        revoke.return_value = datetime.now(tz=timezone.utc)

        response = self.client.post('/api/v1/me/revoke-sessions/')

        self.assertEqual(response.status_code, 204)
        user = User.objects.get(firebase_uid='firebase-uid-1')
        self.assertIsNotNone(user.firebase_tokens_valid_after)
        self.assertTrue(AuditEvent.objects.filter(action='identity.sessions_revoked').exists())

    @mock.patch('api.views.revoke_firebase_sessions')
    @mock.patch('api.authentication.verify_firebase_id_token')
    def test_stale_identity_cannot_revoke_sessions(self, verify, revoke):
        verify.return_value = _claims(auth_time=int(time.time()) - 301)

        response = self.client.post('/api/v1/me/revoke-sessions/')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error']['code'], 'recent_auth_required')
        revoke.assert_not_called()

    def test_protected_student_permission_requires_verified_and_eligible(self):
        user = User.objects.create_user(email='pending@example.com', firebase_uid='pending-uid')
        identity = FirebaseIdentity(
            uid='pending-uid',
            email=user.email,
            email_verified=True,
            auth_time=int(time.time()),
            claims={},
        )
        request = SimpleNamespace(user=user, auth=identity)

        with self.assertRaises(PermissionDenied):
            HasVerifiedEligibleIdentity().has_permission(request, None)


class IdentityFastPathTests(TestCase):
    def identity(self, **overrides):
        values = {'uid': 'fast-uid', 'email': 'fast@example.com', 'email_verified': True,
                  'auth_time': int(time.time()),
                  'claims': {'given_name': 'Fast', 'family_name': 'Student'}}
        values.update(overrides)
        return FirebaseIdentity(**values)

    def locking_queries(self, identity):
        with CaptureQueriesContext(connection) as queries:
            user = resolve_local_identity(identity)
        return user, [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]

    def test_unchanged_approved_user_takes_no_lock(self):
        first = resolve_local_identity(self.identity())
        User.objects.filter(pk=first.pk).update(eligibility_state=EligibilityState.APPROVED,
                                                eligibility_approved_at=django_timezone.now())

        user, locks = self.locking_queries(self.identity())

        self.assertEqual(user.pk, first.pk)
        self.assertEqual(locks, [])

    def test_changed_profile_is_still_synced(self):
        first = resolve_local_identity(self.identity())
        User.objects.filter(pk=first.pk).update(eligibility_state=EligibilityState.APPROVED,
                                                eligibility_approved_at=django_timezone.now())

        user, locks = self.locking_queries(
            self.identity(claims={'given_name': 'Renamed', 'family_name': 'Student'}))

        self.assertNotEqual(locks, [])
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Renamed')

    def test_pending_verified_user_still_accepts_a_new_invitation(self):
        resolve_local_identity(self.identity())
        IdentityInvitation.objects.create(email='fast@example.com')

        user = resolve_local_identity(self.identity())

        self.assertEqual(user.eligibility_state, EligibilityState.APPROVED)
        self.assertTrue(AuditEvent.objects.filter(action='eligibility.invitation_accepted').exists())


class StaffGrantTests(TestCase):
    def test_staff_grant_requires_superuser_and_is_audited(self):
        actor = User.objects.create_user(email='operator@example.com')
        target = User.objects.create_user(email='staff@example.com', firebase_uid='staff-uid')

        with self.assertRaises(CommandError):
            call_command(
                'grant_firebase_staff',
                firebase_uid=target.firebase_uid,
                actor_email=actor.email,
                reason='SEC-100',
            )

        actor.is_staff = True
        actor.is_superuser = True
        actor.save(update_fields=['is_staff', 'is_superuser'])
        call_command(
            'grant_firebase_staff',
            firebase_uid=target.firebase_uid,
            actor_email=actor.email,
            reason='SEC-100',
        )

        target.refresh_from_db()
        self.assertTrue(target.is_staff)
        event = AuditEvent.objects.get(action='staff.granted')
        self.assertEqual(event.actor, actor)
        self.assertEqual(event.resource_id, str(target.pk))

    def test_invitation_command_requires_superuser_and_audits_creation(self):
        actor = User.objects.create_superuser(email='operator@example.com', password=None)

        call_command(
            'invite_identity',
            'Invited@Example.COM',
            actor_email=actor.email,
        )

        invitation = IdentityInvitation.objects.get()
        self.assertEqual(invitation.email, 'invited@example.com')
        self.assertEqual(invitation.created_by, actor)
        self.assertTrue(AuditEvent.objects.filter(action='identity.invitation_created').exists())


@override_settings(FIREBASE_PROJECT_ID='demo-thapargenie')
class ConcurrentIdentityCreationTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_first_requests_create_one_uid(self):
        if connection.vendor != 'postgresql':
            self.skipTest('The concurrency gate runs with TEST_DATABASE_URL on PostgreSQL.')

        identity = FirebaseIdentity(
            uid='concurrent-uid',
            email='concurrent@example.com',
            email_verified=False,
            auth_time=int(time.time()),
            claims={},
        )
        barrier = threading.Barrier(2)
        results = []
        failures = []

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                results.append(resolve_local_identity(identity).pk)
            except Exception as exc:  # pragma: no cover - asserted below
                failures.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(failures)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(User.objects.filter(firebase_uid='concurrent-uid').count(), 1)
