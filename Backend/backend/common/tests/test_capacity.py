from unittest import mock

from django.test import SimpleTestCase, override_settings
from firebase_admin import _http_client

from common import checks
from common.firebase_pool import SDK_DEFAULT_POOL, enlarge_firebase_pool


class FirebasePoolTests(SimpleTestCase):
    def setUp(self):
        original = _http_client.JsonHttpClient.__init__
        self.addCleanup(setattr, _http_client.JsonHttpClient, '__init__', original)
        self.addCleanup(setattr, _http_client.JsonHttpClient, '_pool_enlarged', False)
        _http_client.JsonHttpClient._pool_enlarged = False

    def test_the_sdks_default_size_is_left_alone(self):
        self.assertFalse(enlarge_firebase_pool(SDK_DEFAULT_POOL))
        self.assertFalse(getattr(_http_client.JsonHttpClient, '_pool_enlarged', False))

    def test_new_clients_get_a_pool_as_big_as_the_threads_and_keep_retries(self):
        self.assertTrue(enlarge_firebase_pool(32))
        client = _http_client.JsonHttpClient(base_url='https://example.invalid')
        adapter = client.session.get_adapter('https://example.invalid/')
        self.assertEqual(adapter._pool_maxsize, 32)
        self.assertEqual(adapter.max_retries.total, _http_client.DEFAULT_RETRY_CONFIG.total)

    def test_enlarging_twice_does_not_stack_wrappers(self):
        enlarge_firebase_pool(32)
        wrapped = _http_client.JsonHttpClient.__init__
        enlarge_firebase_pool(32)
        self.assertIs(_http_client.JsonHttpClient.__init__, wrapped)


class ConnectionBudgetTests(SimpleTestCase):
    def run_check(self, workers, threads, pooling):
        env = {'WEB_CONCURRENCY': str(workers), 'GUNICORN_THREADS': str(threads)}
        with mock.patch.dict('os.environ', env), \
                override_settings(DATABASE_TRANSACTION_POOLING=pooling):
            return checks.connection_budget(None)

    def test_the_default_size_is_fine(self):
        self.assertEqual(self.run_check(2, 8, False), [])

    def test_many_threads_on_direct_connections_warn(self):
        [warning] = self.run_check(2, 32, False)
        self.assertEqual(warning.id, 'common.W001')

    def test_many_threads_are_fine_behind_the_transaction_pooler(self):
        self.assertEqual(self.run_check(2, 32, True), [])
