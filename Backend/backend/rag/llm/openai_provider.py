import base64
import json

import openai

from rag.llm.base import (
    BadResponse,
    Generation,
    LLMError,
    Provider,
    QuotaExhausted,
    RetryableError,
    StreamEnd,
    Usage,
)


def _translate(exc):
    if isinstance(exc, openai.RateLimitError):
        code = getattr(exc, 'code', None) or ''
        if code == 'insufficient_quota':
            return QuotaExhausted('OpenAI quota exhausted.')
        retry_after = None
        headers = getattr(getattr(exc, 'response', None), 'headers', {}) or {}
        if str(headers.get('retry-after', '')).replace('.', '', 1).isdigit():
            retry_after = float(headers['retry-after'])
        return RetryableError('OpenAI rate limited.', retry_after=retry_after)
    if isinstance(exc, openai.APITimeoutError | openai.APIConnectionError):
        return RetryableError(f'OpenAI network error: {exc}')
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500 or exc.status_code == 408:
            return RetryableError(f'OpenAI {exc.status_code}.')
        return LLMError(f'OpenAI {exc.status_code}: {exc.message}')
    return exc


def _usage(usage):
    if usage is None:
        return Usage(calls=1)
    return Usage(
        calls=1,
        prompt_tokens=usage.prompt_tokens or 0,
        completion_tokens=usage.completion_tokens or 0,
    )


class OpenAIProvider(Provider):
    name = 'openai'

    def __init__(self, api_key, timeout_seconds=60):
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def embed(self, texts, *, model, dimensions, task, titles=None):
        try:
            response = self._client.embeddings.create(
                model=model, input=list(texts), dimensions=dimensions
            )
        except Exception as exc:
            raise _translate(exc) from exc
        vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        if len(vectors) != len(texts):
            raise BadResponse(f'Expected {len(texts)} embeddings, got {len(vectors)}.')
        return vectors

    def _messages(self, request):
        messages = []
        if request.system:
            messages.append({'role': 'system', 'content': request.system})
        messages += [{'role': m.role, 'content': m.content} for m in request.history]
        messages.append({'role': 'user', 'content': request.prompt})
        return messages

    def _options(self, request):
        options = {
            'model': request.model,
            'messages': self._messages(request),
            'temperature': request.temperature,
            'max_completion_tokens': request.max_output_tokens,
        }
        if request.json_schema is not None:
            options['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'result', 'schema': request.json_schema, 'strict': True},
            }
        return options

    def generate(self, request):
        try:
            response = self._client.chat.completions.create(**self._options(request))
        except Exception as exc:
            raise _translate(exc) from exc
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise BadResponse('OpenAI returned an empty response.')
        if request.json_schema is not None:
            try:
                json.loads(text)
            except ValueError as exc:
                raise BadResponse('OpenAI returned invalid JSON.') from exc
        return Generation(text=text, model=request.model, usage=_usage(response.usage))

    def stream(self, request):
        parts = []
        usage = None
        try:
            stream = self._client.chat.completions.create(
                **self._options(request), stream=True, stream_options={'include_usage': True}
            )
            for chunk in stream:
                usage = chunk.usage or usage
                if chunk.choices and chunk.choices[0].delta.content:
                    piece = chunk.choices[0].delta.content
                    parts.append(piece)
                    yield piece
        except Exception as exc:
            raise _translate(exc) from exc
        if not parts:
            raise BadResponse('OpenAI returned an empty stream.')
        yield StreamEnd(Generation(text=''.join(parts), model=request.model, usage=_usage(usage)))

    def read_pdf(self, *, model, pdf, prompt, max_output_tokens):
        data = base64.b64encode(pdf).decode()
        try:
            response = self._client.chat.completions.create(
                model=model,
                temperature=0,
                max_completion_tokens=max_output_tokens,
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'file',
                                'file': {
                                    'filename': 'document.pdf',
                                    'file_data': f'data:application/pdf;base64,{data}',
                                },
                            },
                            {'type': 'text', 'text': prompt},
                        ],
                    }
                ],
            )
        except Exception as exc:
            raise _translate(exc) from exc
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise BadResponse('OpenAI returned no text for the PDF.')
        return Generation(text=text, model=model, usage=_usage(response.usage))
