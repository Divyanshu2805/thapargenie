from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from common.throttles import AdminWriteThrottle, AskThrottle


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
