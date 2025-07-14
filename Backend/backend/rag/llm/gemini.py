import json
import re

import httpx
from google import genai
from google.genai import errors, types

from rag.llm.base import (
    BadResponse,
    EmbedTask,
    Generation,
    LLMError,
    Provider,
    QuotaExhausted,
    RetryableError,
    StreamEnd,
    Usage,
)

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}
_RETRY_DELAY = re.compile(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'")
_NO_AFC = types.AutomaticFunctionCallingConfig(disable=True)


def _uses_task_prefixes(model):
    # gemini-embedding-001 takes `task_type`; newer embedding models take the task as a
    # text prefix instead.
    return not model.endswith('-001')


def _format_for_embedding(texts, task, titles):
    if task == EmbedTask.QUERY:
        return [f'task: search result | query: {text}' for text in texts]
    titles = titles or [None] * len(texts)
    return [
        f'title: {title or "none"} | text: {text}'
        for text, title in zip(texts, titles, strict=True)
    ]


def _translate(exc):
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return RetryableError(f'Gemini network error: {exc}')
    if not isinstance(exc, errors.APIError):
        return exc
    detail = str(getattr(exc, 'details', '') or exc)
    if exc.code == 402:
        return QuotaExhausted('Gemini prepaid credits are used up.')
    if exc.code == 429 and 'PerDay' in detail:
        return QuotaExhausted('Gemini daily quota exhausted.')
    if exc.code in RETRYABLE_CODES:
        match = _RETRY_DELAY.search(detail)
        delay = float(match.group(1)) if match else None
        return RetryableError(f'Gemini {exc.code}: {exc.message}', retry_after=delay)
    return LLMError(f'Gemini {exc.code}: {exc.message}')


def _usage(metadata):
    if metadata is None:
        return Usage(calls=1)
    return Usage(
        calls=1,
        prompt_tokens=metadata.prompt_token_count or 0,
        completion_tokens=(metadata.candidates_token_count or 0)
        + (metadata.thoughts_token_count or 0),
    )


class GeminiProvider(Provider):
    name = 'gemini'

    def __init__(self, api_key, timeout_seconds=60):
        # The client is kept for the process lifetime; a discarded client closes its
        # HTTP pool and later calls fail.
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    def embed(self, texts, *, model, dimensions, task, titles=None):
        if _uses_task_prefixes(model):
            inputs = _format_for_embedding(texts, task, titles)
            config = types.EmbedContentConfig(output_dimensionality=dimensions)
        else:
            inputs = list(texts)
            config = types.EmbedContentConfig(
                output_dimensionality=dimensions,
                task_type='RETRIEVAL_QUERY' if task == EmbedTask.QUERY else 'RETRIEVAL_DOCUMENT',
            )
        # One Content per text. A bare list of strings is embedded as a single
        # combined input and returns one vector.
        contents = [types.Content(parts=[types.Part(text=text)]) for text in inputs]
        try:
            response = self._client.models.embed_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:
            raise _translate(exc) from exc
        vectors = [list(item.values) for item in response.embeddings or []]
        if len(vectors) != len(texts):
            raise BadResponse(f'Expected {len(texts)} embeddings, got {len(vectors)}.')
        return vectors

    def _config(self, request):
        config = {
            'temperature': request.temperature,
            'max_output_tokens': request.max_output_tokens,
            'automatic_function_calling': _NO_AFC,
        }
        if request.system:
            config['system_instruction'] = request.system
        if request.thinking:
            config['thinking_config'] = types.ThinkingConfig(thinking_level=request.thinking)
        if request.json_schema is not None:
            config['response_mime_type'] = 'application/json'
            config['response_json_schema'] = request.json_schema
        return types.GenerateContentConfig(**config)

    def _contents(self, request):
        contents = [
            types.Content(
                role='model' if message.role == 'assistant' else 'user',
                parts=[types.Part(text=message.content)],
            )
            for message in request.history
        ]
        contents.append(types.Content(role='user', parts=[types.Part(text=request.prompt)]))
        return contents

    def generate(self, request):
        try:
            response = self._client.models.generate_content(
                model=request.model,
                contents=self._contents(request),
                config=self._config(request),
            )
        except Exception as exc:
            raise _translate(exc) from exc
        text = response.text
        if not text:
            raise BadResponse('Gemini returned an empty response.')
        if request.json_schema is not None:
            try:
                json.loads(text)
            except ValueError as exc:
                raise BadResponse('Gemini returned invalid JSON.') from exc
        return Generation(text=text, model=request.model, usage=_usage(response.usage_metadata))

    def stream(self, request):
        parts = []
        metadata = None
        try:
            for chunk in self._client.models.generate_content_stream(
                model=request.model,
                contents=self._contents(request),
                config=self._config(request),
            ):
                metadata = chunk.usage_metadata or metadata
                if chunk.text:
                    parts.append(chunk.text)
                    yield chunk.text
        except Exception as exc:
            raise _translate(exc) from exc
        if not parts:
            raise BadResponse('Gemini returned an empty stream.')
        generation = Generation(text=''.join(parts), model=request.model, usage=_usage(metadata))
        yield StreamEnd(generation)

    def read_pdf(self, *, model, pdf, prompt, max_output_tokens):
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=pdf, mime_type='application/pdf'),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=max_output_tokens,
                    automatic_function_calling=_NO_AFC,
                ),
            )
        except Exception as exc:
            raise _translate(exc) from exc
        if not response.text:
            raise BadResponse('Gemini returned no text for the PDF.')
        return Generation(text=response.text, model=model, usage=_usage(response.usage_metadata))
