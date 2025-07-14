"""Retries, model fallback, batching and usage accounting on top of a Provider."""

import json
import logging
import math
import random
import time
from dataclasses import replace

from rag.llm.base import (
    BadResponse,
    EmbedTask,
    GenerateRequest,
    Message,
    RetryableError,
    StreamEnd,
    Usage,
)

logger = logging.getLogger(__name__)

MAX_RETRY_WAIT = 60.0


def normalize(vector):
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


class LLM:
    """One instance per unit of work (a request, an ingestion job): `usage` accumulates."""

    def __init__(
        self,
        *,
        chat_provider,
        embed_provider,
        chat_model,
        fast_model,
        embed_model,
        dimensions=768,
        max_attempts=3,
        embed_batch_size=50,
        fast_thinking='',
        answer_thinking='',
        sleep=time.sleep,
    ):
        self.chat_provider = chat_provider
        self.embed_provider = embed_provider
        self.chat_model = chat_model
        self.fast_model = fast_model
        self.embed_model = embed_model
        self.dimensions = dimensions
        self.max_attempts = max_attempts
        self.embed_batch_size = embed_batch_size
        self.fast_thinking = fast_thinking
        self.answer_thinking = answer_thinking
        self.usage = Usage()
        self._sleep = sleep

    # -- retry core -----------------------------------------------------------------

    def _wait(self, attempt, error):
        if error.retry_after is not None:
            delay = error.retry_after
        else:
            delay = min(2 ** (attempt - 1), 16) + random.uniform(0, 0.5)  # noqa: S311
        self._sleep(min(delay, MAX_RETRY_WAIT))

    def _with_retries(self, call, attempts=None):
        attempts = attempts or self.max_attempts
        for attempt in range(1, attempts + 1):
            try:
                return call()
            except RetryableError as error:
                if attempt == attempts:
                    raise
                logger.warning('LLM call retrying (%s/%s): %s', attempt, attempts, error)
                self._wait(attempt, error)
        raise AssertionError('unreachable')

    def _models(self, fast):
        # The fast model is the fallback for the chat model, never the other way round.
        if fast or self.chat_model == self.fast_model:
            return [self.fast_model]
        return [self.chat_model, self.fast_model]

    # -- embeddings -----------------------------------------------------------------

    def _embed(self, texts, task, titles, attempts):
        vectors = []
        for start in range(0, len(texts), self.embed_batch_size):
            batch = texts[start : start + self.embed_batch_size]
            batch_titles = titles[start : start + self.embed_batch_size] if titles else None
            result = self._with_retries(
                lambda b=batch, t=batch_titles: self.embed_provider.embed(
                    b, model=self.embed_model, dimensions=self.dimensions, task=task, titles=t
                ),
                attempts=attempts,
            )
            self.usage.calls += 1
            vectors.extend(normalize(vector) for vector in result)
        return vectors

    def embed_documents(self, texts, titles=None, *, attempts=6):
        """Bulk path: more patience for rate limits than interactive calls."""
        return self._embed(list(texts), EmbedTask.DOCUMENT, titles, attempts)

    def embed_queries(self, texts):
        return self._embed(list(texts), EmbedTask.QUERY, None, self.max_attempts)

    # -- generation -----------------------------------------------------------------

    def _request(self, model, prompt, system, history, json_schema, temperature, max_tokens):
        return GenerateRequest(
            model=model,
            prompt=prompt,
            system=system,
            history=tuple(Message(m['role'], m['content']) if isinstance(m, dict) else m
                          for m in history),
            json_schema=json_schema,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    def generate(
        self,
        prompt,
        *,
        system='',
        history=(),
        json_schema=None,
        fast=False,
        temperature=0.2,
        max_output_tokens=2048,
    ):
        last_error = None
        for model in self._models(fast):
            request = self._request(
                model, prompt, system, history, json_schema, temperature, max_output_tokens
            )
            if fast and self.fast_thinking:
                request = replace(request, thinking=self.fast_thinking)
            try:
                result = self._with_retries(lambda r=request: self.chat_provider.generate(r))
            except (RetryableError, BadResponse) as error:
                last_error = error
                logger.warning('Model %s failed, trying fallback: %s', model, error)
                continue
            self.usage.add(result.usage)
            return result
        raise last_error

    def generate_json(self, prompt, *, json_schema, **options):
        result = self.generate(prompt, json_schema=json_schema, **options)
        try:
            return json.loads(result.text)
        except ValueError as exc:
            raise BadResponse('Model returned invalid JSON.') from exc

    def stream(
        self, prompt, *, system='', history=(), temperature=0.2, max_output_tokens=2048
    ):
        """Yield text pieces, then a final StreamEnd.

        Retries and fallback only happen before the first piece is sent: once text has
        reached the user, a failure is surfaced instead of silently restarting.
        """
        last_error = None
        for model in self._models(fast=False):
            request = self._request(
                model, prompt, system, history, None, temperature, max_output_tokens
            )
            if self.answer_thinking and model == self.chat_model:
                request = replace(request, thinking=self.answer_thinking)
            for attempt in range(1, self.max_attempts + 1):
                started = False
                try:
                    for item in self.chat_provider.stream(request):
                        if isinstance(item, StreamEnd):
                            self.usage.add(item.generation.usage)
                        else:
                            started = True
                        yield item
                    return
                except (RetryableError, BadResponse) as error:
                    if started:
                        raise
                    last_error = error
                    if not isinstance(error, RetryableError) or attempt == self.max_attempts:
                        break
                    self._wait(attempt, error)
            logger.warning('Streaming with %s failed, trying fallback: %s', model, last_error)
        raise last_error

    def read_pdf(self, pdf, prompt, *, max_output_tokens=16384):
        last_error = None
        for model in self._models(fast=False):
            try:
                result = self._with_retries(
                    lambda m=model: self.chat_provider.read_pdf(
                        model=m, pdf=pdf, prompt=prompt, max_output_tokens=max_output_tokens
                    )
                )
            except (RetryableError, BadResponse) as error:
                last_error = error
                continue
            self.usage.add(result.usage)
            return result.text
        raise last_error
