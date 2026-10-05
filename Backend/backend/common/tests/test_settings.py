from unittest import mock

from backend.settings.base import database_config
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rag.retrieve import vector_lists

from common.db import apply_session_settings, session_statement


class DatabaseConfigTests(SimpleTestCase):
    def test_rejects_non_postgres(self):
        with self.assertRaises(ImproperlyConfigured):
            database_config('sqlite:///db.sqlite3', ssl_require=False, conn_max_age=0)

    def test_postgres_options(self):
        config = database_config(
            'postgresql://u:p@db.example.com:5432/app', ssl_require=True, conn_max_age=60
        )
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['OPTIONS']['sslmode'], 'require')
        self.assertIn('statement_timeout', config['OPTIONS']['options'])
        self.assertEqual(config['CONN_MAX_AGE'], 60)

    def test_no_ssl_for_local(self):
        config = database_config(
            'postgres://u:p@127.0.0.1:54329/app', ssl_require=False, conn_max_age=0
        )
        self.assertNotIn('sslmode', config['OPTIONS'])


    def test_transaction_pooler_turns_off_server_side_cursors_and_prepared_statements(self):
        url = 'postgresql://u:p@pooler.example.com:6543/app'
        with mock.patch('backend.settings.base.DATABASE_TRANSACTION_POOLING', True):
            pooled = database_config(url, ssl_require=True, conn_max_age=60)
        direct = database_config(url, ssl_require=True, conn_max_age=60)
        self.assertTrue(pooled['DISABLE_SERVER_SIDE_CURSORS'])
        self.assertIsNone(pooled['OPTIONS']['prepare_threshold'])
        self.assertNotIn('prepare_threshold', direct['OPTIONS'])


class SessionSettingsTests(TestCase):
    """Poolers drop startup options, so each connection sets these itself (common/db.py)."""

    def show(self, name):
        with connection.cursor() as cursor:
            cursor.execute(f'SHOW {name}')
            return cursor.fetchone()[0]

    def test_timeouts_and_vector_search_settings_are_applied(self):
        self.assertEqual(self.show('statement_timeout'), '30s')
        self.assertEqual(self.show('lock_timeout'), '5s')
        self.assertEqual(self.show('hnsw.ef_search'), '100')
        self.assertEqual(self.show('hnsw.iterative_scan'), 'relaxed_order')

    def test_skipped_with_a_transaction_pooler(self):
        fake = mock.MagicMock(vendor='postgresql')
        with override_settings(DATABASE_TRANSACTION_POOLING=True):
            apply_session_settings(sender=None, connection=fake)
        fake.cursor.assert_not_called()
        apply_session_settings(sender=None, connection=fake)
        fake.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
            session_statement())

    def test_vector_search_sets_its_own_settings_with_a_transaction_pooler(self):
        with override_settings(DATABASE_TRANSACTION_POOLING=True), \
                CaptureQueriesContext(connection) as queries:
            vector_lists([[0.1] * 768])
        self.assertTrue(any('set_config' in q['sql'] for q in queries))
        with CaptureQueriesContext(connection) as queries:
            vector_lists([[0.1] * 768])
        self.assertEqual(len(queries), 1)


class APIDocsTests(TestCase):
    def test_schema_requires_staff_outside_debug(self):
        response = self.client.get('/api/v1/schema/')
        self.assertIn(response.status_code, (401, 403))

    def test_health_is_open(self):
        self.assertEqual(self.client.get('/health/live/').status_code, 200)
        self.assertEqual(self.client.get('/health/ready/').status_code, 200)
