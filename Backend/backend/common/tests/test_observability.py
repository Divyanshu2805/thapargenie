import json
import logging
import uuid
from datetime import timedelta
from unittest import mock

from api.models import AuditEvent, AuditOutcome
from chat.models import Conversation
from django.core.cache import cache
from django.test import TestCase
from django.urls import get_resolver
from django.utils import timezone
from knowledge.models import Document, DocumentStatus, SourceType
from rest_framework.test import APIClient

from common.observability import JsonFormatter, RequestContextFilter, init_sentry, request_id_var
from common.tests.helpers import client_for, make_user
from common.throttles import ExportThrottle


class LoggingContextTests(TestCase):
    def test_every_log_line_in_a_request_carries_its_request_id(self):
        user = make_user('student@thapar.edu')
        request_id = str(uuid.uuid4())
        with self.assertLogs('thapargenie.access', level='INFO') as logs:
            client_for(user).get('/api/v1/conversations/?q=private-search',
                               HTTP_X_REQUEST_ID=request_id)
        record = logs.records[0]
        # The console handler's filter adds the context; assertLogs uses its own handler.
        RequestContextFilter().filter(record)
        self.assertEqual(record.request_id, request_id)
        self.assertEqual(record.user_id, user.pk)
        # The path is logged, the query string (search terms) never is.
        self.assertIn('GET /api/v1/conversations/ 200', record.getMessage())
        self.assertNotIn('private-search', record.getMessage())

    def test_health_checks_are_not_access_logged(self):
        with self.assertNoLogs('thapargenie.access', level='INFO'):
            self.client.get('/health/live/')

    def test_json_formatter_emits_one_object_with_context(self):
        request_id_var.set('abc')
        record = logging.makeLogRecord({'msg': 'hello %s', 'args': ('world',), 'levelname': 'INFO',
                                        'name': 'x', 'request_id': 'abc', 'status': 200})
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual((payload['message'], payload['request_id'], payload['status']),
                         ('hello world', 'abc', 200))

    def test_sentry_stays_off_without_a_dsn(self):
        self.assertFalse(init_sentry('', environment='test'))


class ServerErrorLoggingTests(TestCase):
    def test_a_5xx_is_logged_with_its_traceback_and_hidden_from_the_client(self):
        user = make_user('student@thapar.edu')
        with mock.patch('chat.views.quota.remaining', side_effect=RuntimeError('boom')), \
                self.assertLogs('thapargenie.errors', level='ERROR') as logs:
            response = client_for(user).get('/api/v1/app-config/')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['error']['code'], 'internal_error')
        self.assertNotIn('boom', response.content.decode())
        self.assertIsNotNone(logs.records[0].exc_info)


class AuthorizationCoverageTests(TestCase):
    """Every /api/v1/ route refuses anonymous callers, except the listed public ones."""

    PUBLIC = {'/api/v1/client-errors/', '/api/v1/shared/<str:token>/'}

    def api_routes(self):
        routes = []

        def walk(patterns, prefix=''):
            for entry in patterns:
                route = prefix + str(entry.pattern)
                if hasattr(entry, 'url_patterns'):
                    walk(entry.url_patterns, route)
                elif route.startswith('api/v1/'):
                    path = '/' + route
                    for token in ('<uuid:conversation_id>', '<uuid:message_id>', '<uuid:source_id>',
                                  '<uuid:document_id>', '<uuid:chunk_id>', '<uuid:feedback_id>',
                                  '<uuid:invitation_id>', '<uuid:notice_id>'):
                        path = path.replace(token, str(uuid.uuid4()))
                    routes.append((path.replace('<int:user_id>', '1'), entry.callback))
        walk(get_resolver().url_patterns)
        return routes

    def test_anonymous_requests_are_refused_everywhere(self):
        anonymous = APIClient()
        checked = 0
        for path, callback in self.api_routes():
            if path in self.PUBLIC:
                continue
            view = getattr(callback, 'view_class', None) or getattr(callback, 'cls', None)
            for method in ('get', 'post', 'patch', 'put', 'delete'):
                if view is not None and not hasattr(view, method):
                    continue
                response = getattr(anonymous, method)(path, {}, format='json')
                self.assertIn(response.status_code, (401, 403), f'{method.upper()} {path}')
                checked += 1
        self.assertGreater(checked, 40)


class AuditTrailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = make_user('student@thapar.edu')

    def test_a_student_probing_the_admin_api_is_audited_once_per_window(self):
        client = client_for(self.student)
        client.get('/api/v1/admin/stats/')
        client.get('/api/v1/admin/stats/')
        events = AuditEvent.objects.filter(action='access.denied')
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual((event.actor, event.outcome, event.resource_id),
                         (self.student, AuditOutcome.DENIED, '/api/v1/admin/stats/'))
        self.assertEqual(event.metadata['method'], 'GET')

    def test_anonymous_refusals_are_logged_not_audited(self):
        APIClient().get('/api/v1/admin/stats/')
        self.assertFalse(AuditEvent.objects.exists())

    def test_delete_all_needs_a_recent_sign_in_and_is_audited(self):
        Conversation.objects.create(user=self.student)
        stale = client_for(self.student, signed_in_seconds_ago=3600)
        refused = stale.delete('/api/v1/conversations/')
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(refused.json()['error']['code'], 'recent_auth_required')
        self.assertTrue(Conversation.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(action='access.denied').exists())

        response = client_for(self.student).delete('/api/v1/conversations/')
        self.assertEqual(response.status_code, 204)
        event = AuditEvent.objects.get(action='privacy.deleted_all')
        self.assertEqual((event.actor, event.metadata), (self.student, {'conversations': 1}))

    def test_export_is_audited_and_rate_limited(self):
        Conversation.objects.create(user=self.student)
        client = client_for(self.student)
        # DRF copies rates onto throttle classes at import; patch the copy.
        with mock.patch.dict(ExportThrottle.THROTTLE_RATES, {'export': '2/hour'}):
            codes = [client.get('/api/v1/me/export/').status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        self.assertEqual(AuditEvent.objects.filter(action='privacy.exported').count(), 2)


class ClientErrorReportTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_reports_are_logged_scrubbed_and_never_echoed(self):
        with self.assertLogs('thapargenie.client', level='WARNING') as logs:
            response = APIClient().post('/api/v1/client-errors/', {
                'message': 'TypeError for student@thapar.edu roll 102103456',
                'stack': 'at x (app.js:1:2)', 'path': '/chat/abc', 'kind': 'render',
            }, format='json')
        self.assertEqual(response.status_code, 204)
        line = logs.records[0].getMessage()
        self.assertIn('[email]', line)
        self.assertIn('[number]', line)
        self.assertNotIn('102103456', line)

    def test_unknown_fields_and_query_strings_are_refused(self):
        client = APIClient()
        self.assertEqual(client.post('/api/v1/client-errors/', {'message': 'x', 'extra': 1},
                                     format='json').status_code, 400)
        self.assertEqual(client.post('/api/v1/client-errors/',
                                     {'message': 'x', 'path': '/chat/?token=abc'},
                                     format='json').status_code, 400)


class RecoveryTests(TestCase):
    def test_interrupted_and_waiting_documents_are_picked_up(self):
        from knowledge import jobs

        def document(title, status):
            return Document.objects.create(title=title, source_type=SourceType.TEXT,
                                           content_hash=title, status=status)

        stuck = document('stuck', DocumentStatus.PROCESSING)
        Document.objects.filter(pk=stuck.pk).update(updated_at=timezone.now() - timedelta(hours=1))
        busy = document('busy', DocumentStatus.PROCESSING)
        waiting = document('waiting', DocumentStatus.QUEUED)

        with mock.patch.object(jobs._executor, 'submit') as submit:
            count = jobs.requeue_stale()

        self.assertEqual(count, 2)
        submitted = {call.args[1] for call in submit.call_args_list}
        self.assertEqual(submitted, {stuck.pk, waiting.pk})
        busy.refresh_from_db()
        self.assertEqual(busy.status, DocumentStatus.PROCESSING)
