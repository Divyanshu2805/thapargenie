"""The local end-to-end switches: offline AI, memory storage, the seed command."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from chat.models import Message
from chat.tests.test_chat import ANALYSIS, ChatTestCase, read_events
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings
from knowledge import storage
from knowledge.storage import MemoryStorage
from rag.analysis import SCHEMA as ANALYSIS_SCHEMA
from rag.llm import use_provider
from rag.llm.base import GenerateRequest
from rag.llm.offline import NOT_FOUND, SUGGESTIONS, OfflineProvider

BACKEND = Path(__file__).resolve().parents[2]
PRODUCTION_ENV = {
    'APP_ENV': 'production',
    'DJANGO_SECRET_KEY': 'test-only-check-key-W7qN4xV9sK2pL8mR5dF1hT6yB3cJ0uE4zA9gC',
    'DJANGO_ALLOWED_HOSTS': 'api.example.invalid',
    'CORS_ALLOWED_ORIGINS': 'https://app.example.invalid',
    'CSRF_TRUSTED_ORIGINS': 'https://app.example.invalid',
    'DATABASE_URL': 'postgresql://app:placeholder@db.example.invalid:5432/thapargpt',
    'FIREBASE_PROJECT_ID': 'example-project',
    'FIREBASE_AUTH_EMULATOR_HOST': '',
    'GEMINI_API_KEY': 'placeholder',
    'CHAT_MODEL': 'model', 'FAST_MODEL': 'model', 'EMBED_MODEL': 'model',
    'SUPABASE_URL': 'https://project.example.invalid',
    'SUPABASE_SERVICE_ROLE_KEY': 'placeholder',
    'LLM_PROVIDER': 'gemini', 'EMBED_PROVIDER': 'gemini', 'STORAGE_BACKEND': 'supabase',
}


def load_production_settings(**overrides):
    env = {**os.environ, **PRODUCTION_ENV, **overrides}
    return subprocess.run(  # noqa: S603 - fixed interpreter and arguments
        [sys.executable, '-c', 'import django, os; '
         'os.environ["DJANGO_SETTINGS_MODULE"] = "backend.settings"; django.setup()'],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60, check=False,
    )


class ProductionRefusesTestSwitchesTests(SimpleTestCase):
    def test_the_baseline_loads(self):
        result = load_production_settings()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_offline_ai_is_refused(self):
        for name in ('LLM_PROVIDER', 'EMBED_PROVIDER'):
            result = load_production_settings(**{name: 'offline'})
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn('offline AI provider is for local tests only', result.stderr)

    def test_memory_storage_is_refused(self):
        result = load_production_settings(STORAGE_BACKEND='memory')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('STORAGE_BACKEND must be supabase in production', result.stderr)


class OfflineProviderTests(ChatTestCase):
    """The offline provider through the real pipeline: search, a cited answer, follow-ups."""

    def setUp(self):
        super().setUp()
        use_provider(OfflineProvider(delay_ms=0))

    def test_a_cited_grounded_answer_from_the_first_source(self):
        events = read_events(self.ask(self.conversation(), content='boys hostel fee?'))
        self.assertEqual(events[-1][0], 'done')
        answer = Message.objects.get(role=Message.Role.ASSISTANT)
        self.assertEqual(answer.answer_type, Message.AnswerType.ANSWERED)
        self.assertTrue(answer.grounded)
        self.assertIn('Boys hostel fee is Rs 1,20,000 per year [1]', answer.content)

        response = self.client.post(f'/api/v1/messages/{answer.pk}/suggestions/')
        self.assertEqual(response.data, {'suggestions': SUGGESTIONS})

    def test_nothing_found(self):
        # With no sources the pipeline answers on its own; the offline text covers the
        # case where the model is called with an empty source list.
        self.document.delete()
        read_events(self.ask(self.conversation(), content='boys hostel fee?'))
        answer = Message.objects.get(role=Message.Role.ASSISTANT)
        self.assertEqual(answer.answer_type, Message.AnswerType.NO_ANSWER)
        self.assertTrue(answer.content.startswith("I couldn't find"))
        request = GenerateRequest(model='m', prompt='<sources>\n(none found)\n</sources>')
        self.assertEqual(''.join(p for p in OfflineProvider(0).stream(request)
                                 if isinstance(p, str)), NOT_FOUND)

    def test_analysis_takes_the_latest_message(self):
        request = GenerateRequest(model='m', prompt='History...\n<message>and for girls?</message>',
                                  json_schema=ANALYSIS_SCHEMA)
        data = json.loads(OfflineProvider(delay_ms=0).generate(request).text)
        self.assertEqual((data['intent'], data['standalone_query']),
                         ('college_query', 'and for girls?'))
        self.assertEqual(set(data), set(ANALYSIS))


class MemoryStorageSwitchTests(SimpleTestCase):
    def test_memory_backend_needs_no_supabase(self):
        storage.use_storage(None)
        self.addCleanup(storage.use_storage, None)
        with override_settings(STORAGE_BACKEND='memory', SUPABASE_URL=''):
            self.assertIsInstance(storage.get_storage(), MemoryStorage)


class SeedCommandGuardTests(SimpleTestCase):
    SAFE = {'FIREBASE_AUTH_EMULATOR_HOST': '127.0.0.1:9099', 'LLM_PROVIDER': 'offline',
            'EMBED_PROVIDER': 'offline', 'STORAGE_BACKEND': 'memory'}

    def refused(self, **overrides):
        with override_settings(**{**self.SAFE, **overrides}), \
                self.assertRaises(CommandError) as caught:
            call_command('seed_e2e')
        return str(caught.exception)

    def test_refuses_without_the_emulator(self):
        self.assertIn('FIREBASE_AUTH_EMULATOR_HOST is not set',
                      self.refused(FIREBASE_AUTH_EMULATOR_HOST=''))

    def test_refuses_real_ai_or_storage(self):
        message = self.refused(LLM_PROVIDER='gemini', STORAGE_BACKEND='supabase')
        self.assertIn('offline AI provider is not selected', message)
        self.assertIn('memory storage is not selected', message)

    def test_refuses_a_remote_database(self):
        with mock.patch('common.management.commands.seed_e2e._database_host',
                        return_value='aws-0-ap-south-1.pooler.supabase.com'):
            self.assertIn('the database is not local', self.refused())

    def test_refuses_production(self):
        with mock.patch.dict(os.environ, {'APP_ENV': 'production'}):
            self.assertIn('APP_ENV is production', self.refused())
