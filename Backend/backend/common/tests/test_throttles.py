import inspect
from types import SimpleNamespace
from unittest import mock

from backend.settings import base as base_settings
from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase, TestCase
from rest_framework.throttling import SimpleRateThrottle

from common import throttles
from common.throttles import AdminWriteThrottle, AskThrottle, InMemory


def request(method='POST', pk=1):
    user = SimpleNamespace(pk=pk, is_authenticated=True)
    return SimpleNamespace(method=method, user=user, META={'REMOTE_ADDR': '127.0.0.1'})


RATES = {'ask': '2/min', 'admin_write': '1/min', 'user': '100/min'}


# Patch the class attribute: DRF copies the rates onto throttle classes at import time,
# so overriding settings alone would not reach them (and restoring them while an
# override is still active would leak the test rates into later tests).
@mock.patch.object(AskThrottle, 'THROTTLE_RATES', RATES)
@mock.patch.object(AdminWriteThrottle, 'THROTTLE_RATES', RATES)
class ThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_ask_limit_is_per_user(self):
        self.assertTrue(AskThrottle().allow_request(request(pk=1), None))
        self.assertTrue(AskThrottle().allow_request(request(pk=1), None))
        self.assertFalse(AskThrottle().allow_request(request(pk=1), None))
        self.assertTrue(AskThrottle().allow_request(request(pk=2), None))

    def test_admin_reads_are_not_counted(self):
        for _ in range(5):
            self.assertTrue(AdminWriteThrottle().allow_request(request('GET'), None))
        self.assertTrue(AdminWriteThrottle().allow_request(request('PATCH'), None))
        self.assertFalse(AdminWriteThrottle().allow_request(request('DELETE'), None))


class MemoryCounterTests(TestCase):
    """Rate-limit counters live in process memory, not in the database cache."""

    def throttle_in(self, memory):
        return type('MemoryAsk', (AskThrottle,), {'cache': memory})()

    def test_counting_makes_no_database_queries(self):
        memory = LocMemCache('queries-test', {})
        self.addCleanup(memory.clear)
        with mock.patch.object(AskThrottle, 'THROTTLE_RATES', RATES):
            with self.assertNumQueries(0):
                throttle = self.throttle_in(memory)
                self.assertTrue(throttle.allow_request(request(pk=7), None))
                self.assertTrue(self.throttle_in(memory).allow_request(request(pk=7), None))
                self.assertFalse(self.throttle_in(memory).allow_request(request(pk=7), None))

    def test_each_worker_counts_on_its_own(self):
        first, second = LocMemCache('worker-1', {}), LocMemCache('worker-2', {})
        self.addCleanup(first.clear)
        self.addCleanup(second.clear)
        with mock.patch.object(AskThrottle, 'THROTTLE_RATES', RATES):
            for _ in range(2):
                self.assertTrue(self.throttle_in(first).allow_request(request(), None))
            self.assertFalse(self.throttle_in(first).allow_request(request(), None))
            # Another process has not seen those requests: the documented trade-off.
            self.assertTrue(self.throttle_in(second).allow_request(request(), None))


class MemoryConfigurationTests(SimpleTestCase):
    def test_every_throttle_class_counts_in_memory(self):
        classes = [c for _, c in inspect.getmembers(throttles, inspect.isclass)
                   if issubclass(c, SimpleRateThrottle) and c.__module__ == throttles.__name__]
        self.assertGreaterEqual(len(classes), 9)
        for throttle in classes:
            with self.subTest(throttle=throttle.__name__):
                self.assertTrue(issubclass(throttle, InMemory))
                self.assertIs(throttle.cache, InMemory.cache)

    def test_the_default_throttle_is_the_memory_one(self):
        self.assertEqual(base_settings.REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'],
                         ('common.throttles.UserThrottle',))

    def test_deployed_settings_keep_throttles_in_a_bounded_memory_cache(self):
        configured = base_settings.CACHES['throttle']
        self.assertTrue(configured['BACKEND'].endswith('locmem.LocMemCache'))
        self.assertEqual(configured['OPTIONS']['MAX_ENTRIES'], 10000)
        # Everything else (coverage, audit de-duplication) stays shared in the database.
        self.assertTrue(base_settings.CACHES['default']['BACKEND'].endswith('db.DatabaseCache'))
