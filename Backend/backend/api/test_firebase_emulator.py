import json
import os
import time
import urllib.request
import uuid
from unittest import skipUnless

from django.test import TransactionTestCase
from firebase_admin import auth
from rest_framework.test import APIClient
from userauths.models import IdentityInvitation

from api.firebase import get_firebase_app

RUN_EMULATOR = bool(os.getenv('RUN_FIREBASE_EMULATOR_TESTS')) and bool(
    os.getenv('FIREBASE_AUTH_EMULATOR_HOST')
)


def _sign_in(project_id, email, password):
    host = os.environ['FIREBASE_AUTH_EMULATOR_HOST']
    url = (
        f'http://{host}/identitytoolkit.googleapis.com/v1/'
        'accounts:signInWithPassword?key=emulator-fake-key'
    )
    payload = json.dumps(
        {'email': email, 'password': password, 'returnSecureToken': True}
    ).encode()
    request = urllib.request.Request(  # noqa: S310 - fixed local emulator URL
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read())['idToken']


@skipUnless(RUN_EMULATOR, 'Firebase Auth emulator is not enabled for this test run.')
class FirebaseEmulatorIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.project_id = 'demo-thapargenie'
        self.uid = f'test-{uuid.uuid4()}'
        self.email = f'{self.uid}@example.com'
        self.password = 'Synthetic-test-password-123!'  # noqa: S105
        self.app = get_firebase_app()
        auth.create_user(
            uid=self.uid,
            email=self.email,
            email_verified=True,
            password=self.password,
            app=self.app,
        )
        IdentityInvitation.objects.create(email=self.email)

    def tearDown(self):
        auth.delete_user(self.uid, app=self.app)

    def test_emulator_token_reaches_me_endpoint(self):
        token = _sign_in(self.project_id, self.email, self.password)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['uid'], self.uid)
        self.assertEqual(response.json()['onboarding_status'], 'ready')

    def test_disabled_emulator_identity_is_rejected(self):
        token = _sign_in(self.project_id, self.email, self.password)
        auth.update_user(self.uid, disabled=True, app=self.app)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)

    def test_revoked_emulator_identity_is_rejected(self):
        token = _sign_in(self.project_id, self.email, self.password)
        time.sleep(1.1)
        auth.revoke_refresh_tokens(self.uid, app=self.app)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = client.get('/api/v1/me/')

        self.assertEqual(response.status_code, 401)
