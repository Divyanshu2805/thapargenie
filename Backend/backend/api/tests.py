import logging
from unittest import mock
from uuid import UUID

from backend.logging import RedactSecretsFilter
from django.conf import settings
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from userauths.models import User

from api.errors import api_exception_handler
from api.models import AuditEvent, AuditOutcome


class TestStageZeroContainment(TestCase):
    legacy_paths = (
        '/api/v1/user/register/',
        '/api/v1/user/token/',
        '/api/v1/user/token/refresh/',
        '/api/v1/user/password-reset/synthetic@example.invalid/',
        '/api/v1/user/password-change/',
    )

    def test_legacy_student_auth_routes_are_not_mounted(self):
        for path in self.legacy_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)
                response = self.client.post(path, data={}, content_type='application/json')
                self.assertEqual(response.status_code, 404)

    def test_runtime_does_not_trust_the_old_development_signing_key(self):
        self.assertGreaterEqual(len(settings.SECRET_KEY), 50)
        self.assertFalse(settings.SECRET_KEY.startswith('django' + '-insecure-'))

    def test_service_index_and_health_checks_are_minimal(self):
        index = self.client.get('/')
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.json(), {'service': 'thapargenie-api'})

        live = self.client.get('/health/live/')
        self.assertEqual(live.status_code, 200)
        UUID(live.headers['X-Request-ID'])

        ready = self.client.get('/health/ready/')
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {'status': 'ready'})

    def test_failed_readiness_check_is_logged(self):
        with mock.patch('api.views.connection.cursor', side_effect=RuntimeError('down')), \
                self.assertLogs('api.views', level='WARNING') as captured:
            response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertIsNotNone(captured.records[0].exc_info)

    def test_invalid_request_id_is_replaced(self):
        response = self.client.get('/health/live/', HTTP_X_REQUEST_ID='not-a-valid-id')
        UUID(response.headers['X-Request-ID'])
        self.assertNotEqual(response.headers['X-Request-ID'], 'not-a-valid-id')

    def test_api_error_envelope_contains_request_id(self):
        request = Request(APIRequestFactory().get('/api/v1/private/'))
        request.request_id = '2f44becc-c461-44c9-8814-b3ee6b3619b4'
        response = api_exception_handler(
            NotAuthenticated('Sign in required.'),
            {'request': request},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                'error': {
                    'code': 'not_authenticated',
                    'message': 'Sign in required.',
                    'request_id': request.request_id,
                },
            },
        )

    def test_unexpected_api_exception_is_generic_and_request_id_backed(self):
        request = Request(APIRequestFactory().get('/api/v1/private/'))
        request.request_id = '82d879a7-76c8-49fd-909a-342c9e8ebd50'
        with self.assertLogs('api.errors', level='ERROR') as captured:
            response = api_exception_handler(
                RuntimeError('database password=never-return-this'),
                {'request': request},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data,
            {
                'error': {
                    'code': 'internal_error',
                    'message': 'The request could not be completed.',
                    'request_id': request.request_id,
                }
            },
        )
        self.assertNotIn('never-return-this', str(response.data))
        self.assertNotIn('never-return-this', '\n'.join(captured.output))

    def test_log_filter_redacts_common_secret_fields(self):
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='password=hunter2 Authorization: Bearer signed-token',
            args=(),
            exc_info=None,
        )
        self.assertTrue(RedactSecretsFilter().filter(record))
        rendered = record.getMessage()
        self.assertNotIn('hunter2', rendered)
        self.assertNotIn('signed-token', rendered)
        self.assertEqual(record.request_id, '-')


class TestAuditFoundation(TestCase):
    def test_audit_event_uses_uuid_and_preserves_metadata_only(self):
        actor = User.objects.create_user(email='audit-actor@example.com')
        event = AuditEvent.objects.create(
            actor=actor,
            action='identity.created',
            resource_type='user',
            resource_id=str(actor.pk),
            outcome=AuditOutcome.SUCCEEDED,
            metadata={'source': 'synthetic-test'},
        )

        self.assertEqual(event.actor, actor)
        self.assertEqual(event.metadata, {'source': 'synthetic-test'})
        UUID(str(event.id))
