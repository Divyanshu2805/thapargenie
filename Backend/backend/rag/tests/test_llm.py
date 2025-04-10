import math

from django.test import SimpleTestCase
from google.genai import errors

from rag.llm.base import BadResponse, EmbedTask, LLMError, QuotaExhausted, RetryableError, StreamEnd
from rag.llm.client import LLM
from rag.llm.fake import FakeProvider
from rag.llm.gemini import _format_for_embedding, _translate, _uses_task_prefixes


def make_llm(provider, **options):
    return LLM(
        chat_provider=provider,
        embed_provider=provider,
        chat_model='chat',
        fast_model='fast',
        embed_model='embed',
        dimensions=options.pop('dimensions', 32),
        embed_batch_size=options.pop('embed_batch_size', 2),
        sleep=lambda _seconds: None,
        **options,
    )


class RetryAndFallbackTests(SimpleTestCase):
    def test_retries_transient_errors(self):
        fake = FakeProvider()
        fake.fail_next(RetryableError('busy'), RetryableError('busy'))
        fake.queue('answer')
        llm = make_llm(fake)
        self.assertEqual(llm.generate('q').text, 'answer')
        self.assertEqual(llm.usage.calls, 1)

    def test_falls_back_to_fast_model(self):
        fake = FakeProvider()
        fake.fail_next(*[RetryableError('overloaded')] * 3)
        fake.queue('from fast')
        result = make_llm(fake).generate('q')
        self.assertEqual(result.model, 'fast')
        self.assertEqual([r.model for r in fake.requests], ['chat', 'chat', 'chat', 'fast'])

    def test_fast_calls_do_not_fall_back_upwards(self):
        fake = FakeProvider()
        fake.fail_next(*[RetryableError('busy')] * 3)
        with self.assertRaises(RetryableError):
            make_llm(fake).generate('q', fast=True)
        self.assertEqual({r.model for r in fake.requests}, {'fast'})

    def test_non_retryable_errors_propagate(self):
        fake = FakeProvider()
        fake.fail_next(QuotaExhausted('daily quota'))
        with self.assertRaises(QuotaExhausted):
            make_llm(fake).generate('q')

    def test_retry_after_is_respected_and_capped(self):
        waits = []
        fake = FakeProvider()
        fake.fail_next(RetryableError('slow down', retry_after=5), RetryableError('x', 999))
        fake.queue('ok')
        llm = make_llm(fake)
        llm._sleep = waits.append
        llm.generate('q')
        self.assertEqual(waits, [5, 60.0])

    def test_generate_json(self):
        fake = FakeProvider()
        fake.queue({'intent': 'college_query'})
        schema = {'type': 'object'}
        self.assertEqual(
            make_llm(fake).generate_json('q', json_schema=schema),
            {'intent': 'college_query'},
        )

    def test_history_dicts_become_messages(self):
        fake = FakeProvider()
        make_llm(fake).generate('q', history=[{'role': 'user', 'content': 'hi'}])
        self.assertEqual(fake.requests[0].history[0].content, 'hi')


class StreamTests(SimpleTestCase):
    def test_stream_yields_pieces_then_end(self):
        fake = FakeProvider()
        fake.queue('Hostel fee is 1,20,000.')
        items = list(make_llm(fake).stream('q'))
        self.assertIsInstance(items[-1], StreamEnd)
        self.assertEqual(''.join(items[:-1]), 'Hostel fee is 1,20,000.')

    def test_stream_retries_before_first_piece(self):
        fake = FakeProvider()
        fake.fail_next(RetryableError('busy'))
        fake.queue('ok')
        items = list(make_llm(fake).stream('q'))
        self.assertEqual(items[0], 'ok')

    def test_stream_never_restarts_after_text_was_sent(self):
        class Flaky(FakeProvider):
            def stream(self, request):
                yield 'partial '
                raise RetryableError('connection dropped')

        stream = make_llm(Flaky()).stream('q')
        self.assertEqual(next(stream), 'partial ')
        with self.assertRaises(RetryableError):
            next(stream)


class EmbeddingTests(SimpleTestCase):
    def test_batches_and_normalizes(self):
        fake = FakeProvider()
        vectors = make_llm(fake).embed_documents(['a b', 'b c', 'c d', 'd e', 'e f'])
        self.assertEqual(len(vectors), 5)
        self.assertEqual([len(texts) for texts, _ in fake.embed_calls], [2, 2, 1])
        for vector in vectors:
            self.assertAlmostEqual(math.sqrt(sum(x * x for x in vector)), 1.0, places=6)

    def test_query_task_is_passed(self):
        fake = FakeProvider()
        make_llm(fake).embed_queries(['hostel fee'])
        self.assertEqual(fake.embed_calls[0][1], EmbedTask.QUERY)

    def test_related_texts_are_closer(self):
        fake = FakeProvider()
        query, near, far = make_llm(fake, dimensions=256).embed_documents(
            ['hostel fee first year', 'first year hostel fee structure', 'library opening hours']
        )
        dot = lambda a, b: sum(x * y for x, y in zip(a, b, strict=True))  # noqa: E731
        self.assertGreater(dot(query, near), dot(query, far))


class GeminiHelperTests(SimpleTestCase):
    def test_prefix_models(self):
        self.assertTrue(_uses_task_prefixes('gemini-embedding-2'))
        self.assertFalse(_uses_task_prefixes('gemini-embedding-001'))

    def test_prefix_formats(self):
        self.assertEqual(
            _format_for_embedding(['fees'], EmbedTask.QUERY, None),
            ['task: search result | query: fees'],
        )
        self.assertEqual(
            _format_for_embedding(['x', 'y'], EmbedTask.DOCUMENT, ['Fees', None]),
            ['title: Fees | text: x', 'title: none | text: y'],
        )

    def _api_error(self, code, details):
        return errors.APIError(code, {'error': {'code': code, 'message': 'm', 'details': details}})

    def test_rate_limit_with_retry_delay(self):
        details = [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '33s'}]
        error = _translate(self._api_error(429, details))
        self.assertIsInstance(error, RetryableError)
        self.assertEqual(error.retry_after, 33.0)

    def test_daily_quota_is_not_retried(self):
        details = [{'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel'}]}]
        self.assertIsInstance(_translate(self._api_error(429, details)), QuotaExhausted)

    def test_depleted_prepaid_credits_are_not_retried(self):
        self.assertIsInstance(_translate(self._api_error(402, [])), QuotaExhausted)

    def test_overload_is_retryable(self):
        self.assertIsInstance(_translate(self._api_error(503, [])), RetryableError)

    def test_bad_request_is_fatal(self):
        error = _translate(self._api_error(400, []))
        self.assertIsInstance(error, LLMError)
        self.assertNotIsInstance(error, RetryableError | BadResponse)
