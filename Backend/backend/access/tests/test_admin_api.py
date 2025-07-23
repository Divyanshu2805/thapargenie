from datetime import timedelta

from api.identity import FirebaseIdentity, resolve_local_identity
from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from django.test import TestCase
from django.utils import timezone
from userauths.models import EligibilityState, IdentityInvitation, User

BASE = '/api/v1/admin'


class AccessTestCase(TestCase):
    def setUp(self):
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.client = client_for(self.admin)


class InvitationTests(AccessTestCase):
    def test_create_normalises_and_audits(self):
        response = self.client.post(f'{BASE}/invitations/',
                                    {'email': ' New.Student@Thapar.EDU ', 'expires_in_days': 7},
                                    format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['email'], 'new.student@thapar.edu')
        self.assertEqual(response.data['status'], 'pending')
        invitation = IdentityInvitation.objects.get()
        self.assertEqual(invitation.created_by, self.admin)
        self.assertAlmostEqual(invitation.expires_at, timezone.now() + timedelta(days=7),
                               delta=timedelta(minutes=1))
        event = AuditEvent.objects.get(action='identity.invitation_created')
        self.assertEqual((event.actor, event.resource_id, event.metadata),
                         (self.admin, str(invitation.pk), {'method': 'admin_api'}))

    def test_duplicate_is_case_insensitive(self):
        self.client.post(f'{BASE}/invitations/', {'email': 'a@thapar.edu'}, format='json')
        response = self.client.post(f'{BASE}/invitations/', {'email': 'A@THAPAR.edu'},
                                    format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'invitation_exists')

    def test_validation(self):
        for body in ({'email': 'not-an-email'}, {'email': 'a@b.co', 'expires_in_days': 0},
                     {'email': 'a@b.co', 'is_active': False}):
            response = self.client.post(f'{BASE}/invitations/', body, format='json')
            self.assertEqual(response.status_code, 400, body)

    def test_list_and_search(self):
        IdentityInvitation.objects.create(email='one@thapar.edu')
        IdentityInvitation.objects.create(email='two@thapar.edu', is_active=False)
        response = self.client.get(f'{BASE}/invitations/', {'q': 'two'})
        [item] = response.data['results']
        self.assertEqual((item['email'], item['status']), ('two@thapar.edu', 'inactive'))

    def test_invitation_approves_the_student_on_sign_in(self):
        self.client.post(f'{BASE}/invitations/', {'email': 'fresh@thapar.edu'}, format='json')
        identity = FirebaseIdentity('uid-fresh', 'fresh@thapar.edu', True, 0, {})
        user = resolve_local_identity(identity)
        self.assertEqual(user.eligibility_state, EligibilityState.APPROVED)
        response = self.client.get(f'{BASE}/invitations/')
        self.assertEqual(response.data['results'][0]['status'], 'accepted')

    def test_delete_pending_but_not_used(self):
        pending = IdentityInvitation.objects.create(email='p@thapar.edu')
        response = self.client.delete(f'{BASE}/invitations/{pending.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(IdentityInvitation.objects.filter(pk=pending.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='identity.invitation_deleted',
                                                  resource_id=str(pending.pk)).exists())

        student = make_user('used@thapar.edu')
        used = IdentityInvitation.objects.create(email='used@thapar.edu', is_active=False,
                                                 accepted_by=student,
                                                 accepted_at=timezone.now())
        response = self.client.delete(f'{BASE}/invitations/{used.pk}/')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'invitation_used')


class UserTests(AccessTestCase):
    def test_list_search_and_filter(self):
        make_user('pending@thapar.edu', state=EligibilityState.PENDING)
        make_user('approved@thapar.edu')
        response = self.client.get(f'{BASE}/users/', {'eligibility_state': 'pending'})
        self.assertEqual([u['email'] for u in response.data['results']],
                         ['pending@thapar.edu'])
        response = self.client.get(f'{BASE}/users/', {'q': 'approv'})
        self.assertEqual([u['email'] for u in response.data['results']],
                         ['approved@thapar.edu'])
        self.assertNotIn('firebase_uid', response.data['results'][0])
        response = self.client.get(f'{BASE}/users/', {'eligibility_state': 'nope'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('eligibility_state', response.data['error']['fields'])

    def test_approve_and_suspend_are_audited(self):
        student = make_user('pending@thapar.edu', state=EligibilityState.PENDING)
        response = self.client.patch(f'{BASE}/users/{student.pk}/',
                                     {'eligibility_state': 'approved'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        student.refresh_from_db()
        self.assertEqual(student.eligibility_state, EligibilityState.APPROVED)
        self.assertIsNotNone(student.eligibility_approved_at)

        response = self.client.patch(f'{BASE}/users/{student.pk}/', {
            'eligibility_state': 'suspended', 'reason': 'Graduated',
        }, format='json')
        self.assertEqual(response.data['eligibility_state'], 'suspended')
        events = AuditEvent.objects.filter(action='eligibility.changed').order_by('created_at')
        self.assertEqual(
            [(e.metadata['previous'], e.metadata['state']) for e in events],
            [('pending', 'approved'), ('approved', 'suspended')],
        )
        self.assertEqual(events.last().metadata['reason'], 'Graduated')

        # A suspended student is refused by the student API straight away.
        student.refresh_from_db()
        refused = client_for(student).get('/api/v1/conversations/')
        self.assertEqual(refused.status_code, 403)

    def test_same_state_is_a_no_op(self):
        student = make_user('s@thapar.edu')
        self.client.patch(f'{BASE}/users/{student.pk}/', {'eligibility_state': 'approved'},
                          format='json')
        self.assertFalse(AuditEvent.objects.filter(action='eligibility.changed').exists())

    def test_guards(self):
        other_staff = make_user('staff2@thapar.edu', staff=True)
        for target, code in ((self.admin, 'own_account'), (other_staff, 'staff_account')):
            response = self.client.patch(f'{BASE}/users/{target.pk}/',
                                         {'eligibility_state': 'suspended'}, format='json')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data['error']['code'], code)
        student = make_user('s@thapar.edu')
        for body in ({'eligibility_state': 'pending'}, {'is_staff': True},
                     {'eligibility_state': 'approved', 'is_staff': True}):
            response = self.client.patch(f'{BASE}/users/{student.pk}/', body, format='json')
            self.assertEqual(response.status_code, 400, body)
        student.refresh_from_db()
        self.assertFalse(student.is_staff)
        self.assertEqual(self.client.patch(f'{BASE}/users/999999/',
                                           {'eligibility_state': 'approved'},
                                           format='json').status_code, 404)


class AuditLogTests(AccessTestCase):
    def test_list_and_filters(self):
        self.client.post(f'{BASE}/invitations/', {'email': 'a@thapar.edu'}, format='json')
        self.client.patch(f'{BASE}/settings/', {'banner_text': 'Hello'}, format='json')
        response = self.client.get(f'{BASE}/audit-log/')
        self.assertEqual([e['action'] for e in response.data['results']],
                         ['settings.updated', 'identity.invitation_created'])
        self.assertEqual(response.data['results'][0]['actor_email'], 'admin@thapar.edu')

        response = self.client.get(f'{BASE}/audit-log/', {'action': 'identity.'})
        self.assertEqual([e['action'] for e in response.data['results']],
                         ['identity.invitation_created'])
        response = self.client.get(f'{BASE}/audit-log/', {'action': 'identity'})
        self.assertEqual(response.data['results'], [])
        response = self.client.get(f'{BASE}/audit-log/', {'resource_type': 'identity_invitation'})
        self.assertEqual([e['action'] for e in response.data['results']],
                         ['identity.invitation_created'])

    def test_malformed_filters_are_refused(self):
        for params in ({'action': 'Identity.'}, {'action': 'identity..created'},
                       {'action': "x' or 1=1"}, {'action': 'a' * 101},
                       {'resource_type': 'user.'}, {'resource_id': 'a b'},
                       {'resource_id': 'a' * 129}):
            response = self.client.get(f'{BASE}/audit-log/', params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn(next(iter(params)), response.data['error']['fields'])

    def test_audit_log_is_read_only(self):
        response = self.client.post(f'{BASE}/audit-log/', {}, format='json')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(User.objects.count(), 1)
