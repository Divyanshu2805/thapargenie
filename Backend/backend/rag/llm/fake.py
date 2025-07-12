"""Deterministic provider for tests and offline development.

Embeddings are hashed bags of words, so texts that share words are close in cosine
space. Generations are served from a queue; with an empty queue it echoes the prompt.
"""

import hashlib
import json
import math
import re
from collections import deque

from rag.llm.base import Generation, Provider, StreamEnd, Usage

_WORD = re.compile(r'[a-z0-9]+')


def hashed_embedding(text, dimensions):
    vector = [0.0] * dimensions
    for word in _WORD.findall(text.lower()):
        digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], 'little') % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class FakeProvider(Provider):
    name = 'fake'

    def __init__(self):
        self.responses = deque()
        self.requests = []
        self.embed_calls = []
        self.failures = deque()

    def queue(self, *responses):
        """Queue replies. Dicts/lists are sent as JSON; exceptions are raised."""
        for response in responses:
            self.responses.append(response)

    def fail_next(self, *exceptions):
        self.failures.extend(exceptions)

    def _maybe_fail(self):
        if self.failures:
            raise self.failures.popleft()

    def _next_text(self, request):
        self.requests.append(request)
        self._maybe_fail()
        if self.responses:
            reply = self.responses.popleft()
            if isinstance(reply, Exception):
                raise reply
            return json.dumps(reply) if isinstance(reply, dict | list) else reply
        return f'echo: {request.prompt}'

    def embed(self, texts, *, model, dimensions, task, titles=None):
        self.embed_calls.append((list(texts), task))
        self._maybe_fail()
        return [hashed_embedding(text, dimensions) for text in texts]

    def generate(self, request):
        text = self._next_text(request)
        return Generation(text=text, model=request.model, usage=Usage(calls=1))

    def stream(self, request):
        text = self._next_text(request)
        for word in re.findall(r'\S+\s*', text):
            yield word
        yield StreamEnd(Generation(text=text, model=request.model, usage=Usage(calls=1)))

    def read_pdf(self, *, model, pdf, prompt, max_output_tokens):
        self.requests.append(('read_pdf', model, len(pdf)))
        self._maybe_fail()
        text = self.responses.popleft() if self.responses else '# Document\n\nParsed text.'
        return Generation(text=text, model=model, usage=Usage(calls=1))
