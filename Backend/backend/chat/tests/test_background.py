import importlib.util
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from chat import background


class BoundedBackgroundQueueTests(SimpleTestCase):
    """A fresh one-thread pool is held busy so jobs queue up behind it."""

    def setUp(self):
        self.release = threading.Event()
        self.started = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1)
        for patcher in (mock.patch.object(background, '_executor', self.pool),
                        mock.patch.object(background, '_queued', 0),
                        mock.patch.object(background, 'MAX_QUEUED', 3),
                        mock.patch.object(background, '_wrap', lambda f, *a: f(*a))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.pool.shutdown, wait=True, cancel_futures=True)
        self.addCleanup(self.release.set)

    def _blocker(self):
        self.started.set()
        self.release.wait(5)

    def test_jobs_beyond_the_limit_are_dropped(self):
        ran = []
        background.submit(self._blocker)
        self.assertTrue(self.started.wait(5))
        with self.assertLogs('chat.background', 'WARNING') as logs:
            for index in range(5):
                background.submit(ran.append, index)
        self.assertEqual(len(logs.records), 3)  # 5 submitted, 2 fit
        self.release.set()
        self.pool.shutdown(wait=True)
        self.assertEqual(ran, [0, 1])  # blocker + 2 queued filled the 3 slots

    def test_slots_come_back_when_jobs_finish(self):
        done = threading.Event()
        for _ in range(3):
            background.submit(done.set)
        self.pool.shutdown(wait=True)
        self.assertEqual(background._queued, 0)

    def test_shutdown_cancels_queued_jobs_and_frees_their_slots(self):
        ran = []
        background.submit(self._blocker)
        self.assertTrue(self.started.wait(5))
        background.submit(ran.append, 'queued')
        self.assertEqual(background._queued, 2)
        background.shutdown()
        self.assertEqual(background._queued, 1)  # only the running blocker is left
        self.release.set()
        self.pool.shutdown(wait=True)
        self.assertEqual(ran, [])

    def test_submit_after_shutdown_is_skipped_quietly(self):
        background.shutdown()
        with self.assertLogs('chat.background', 'INFO'):
            background.submit(lambda: None)
        self.assertEqual(background._queued, 0)


class GunicornWorkerExitTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Path(__file__).resolve().parents[2] / 'gunicorn.conf.py'
        spec = importlib.util.spec_from_file_location('gunicorn_conf_under_test', path)
        cls.conf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.conf)

    def test_worker_exit_drops_queued_work_in_the_worker(self):
        worker = mock.Mock(pid=os.getpid())
        with mock.patch.object(background, 'shutdown') as chat_shutdown, \
                mock.patch('knowledge.jobs.shutdown') as ingest_shutdown:
            self.conf.worker_exit(None, worker)
        chat_shutdown.assert_called_once_with()
        ingest_shutdown.assert_called_once_with()

    def test_worker_exit_does_nothing_in_the_master(self):
        worker = mock.Mock(pid=os.getpid() + 1)
        with mock.patch.object(background, 'shutdown') as chat_shutdown:
            self.conf.worker_exit(None, worker)
        chat_shutdown.assert_not_called()

    def test_recycling_is_rare_with_proportional_jitter(self):
        self.assertGreaterEqual(self.conf.max_requests, 10000)
        self.assertEqual(self.conf.max_requests_jitter, self.conf.max_requests // 10)
