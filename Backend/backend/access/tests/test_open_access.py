"""The approval switch: with approval off, verified sign-ins get in directly."""

import time

from api.identity import FirebaseIdentity, resolve_local_identity
from api.models import AuditEvent
from chat.admin_services import update_settings
from chat.models import ChatSettings
from django.test import TestCase, override_settings
from django.utils import timezone
from userauths.models import EligibilityState, User


def identity(**overrides):
    values = {'uid': 'open-uid', 'email': 'open@example.com', 'email_verified': True,
              'auth_time': int(time.time()), 'claims': {}}
    values.update(overrides)
    return FirebaseIdentity(**values)


def require_approval(value):
    ChatSettings.objects.update_or_create(pk=1, defaults={'require_approval': value})
    ChatSettings.forget()


class OpenAccessTests(TestCase):
    def tearDown(self):
        ChatSettings.forget()

    def test_approval_is_required_by_default(self):
        user = resolve_local_identity(identity())
        self.assertEqual(user.eligibility_state, EligibilityState.PENDING)
        self.assertFalse(AuditEvent.objects.filter(action='eligibility.auto_approved').exists())

    def test_open_access_approves_a_new_verified_user_and_audits_it(self):
        require_approval(False)
        user = resolve_local_identity(identity())
        user.refresh_from_db()
        self.assertEqual(user.eligibility_state, EligibilityState.APPROVED)
        self.assertIsNotNone(user.eligibility_approved_at)
        event = AuditEvent.objects.get(action='eligibility.auto_approved')
        self.assertEqual((event.actor, event.resource_id), (user, str(user.pk)))
        self.assertEqual(event.metadata, {'method': 'open_access'})

    def test_waiting_users_get_in_on_their_next_request(self):
        waiting = resolve_local_identity(identity())
        require_approval(False)
        self.assertEqual(resolve_local_identity(identity()).pk, waiting.pk)
        waiting.refresh_from_db()
        self.assertEqual(waiting.eligibility_state, EligibilityState.APPROVED)

    def test_unverified_email_still_waits(self):
        require_approval(False)
        user = resolve_local_identity(identity(email_verified=False))
        self.assertEqual(user.eligibility_state, EligibilityState.PENDING)

    def test_denied_and_suspended_users_stay_blocked(self):
        for state in (EligibilityState.DENIED, EligibilityState.SUSPENDED):
            with self.subTest(state=state):
                me = identity(uid=f'uid-{state}', email=f'{state}@example.com')
                user = resolve_local_identity(me)
                User.objects.filter(pk=user.pk).update(eligibility_state=state)
                require_approval(False)
                user = resolve_local_identity(me)
                self.assertEqual(user.eligibility_state, state)
                require_approval(True)

    def test_switching_approval_back_on_keeps_approved_users(self):
        require_approval(False)
        resolve_local_identity(identity())
        require_approval(True)
        self.assertEqual(resolve_local_identity(identity()).eligibility_state,
                         EligibilityState.APPROVED)
        newcomer = resolve_local_identity(identity(uid='new-uid', email='new@example.com'))
        self.assertEqual(newcomer.eligibility_state, EligibilityState.PENDING)

    @override_settings(IDENTITY_OPEN_ACCESS='')
    def test_auth_apps_alone_always_require_approval(self):
        require_approval(False)
        self.assertEqual(resolve_local_identity(identity()).eligibility_state,
                         EligibilityState.PENDING)

    def test_admin_can_switch_it_through_settings(self):
        admin = User.objects.create_user(email='admin@example.com', is_staff=True,
                                         eligibility_state=EligibilityState.APPROVED,
                                         eligibility_approved_at=timezone.now())
        update_settings({'require_approval': False}, user=admin)
        self.assertFalse(ChatSettings.load(fresh=True).require_approval)
        event = AuditEvent.objects.get(action='settings.updated')
        self.assertEqual(event.metadata['values'], {'require_approval': [True, False]})
