"""A deterministic, free stand-in for the AI provider, for local end-to-end runs.

Selected with LLM_PROVIDER=offline / EMBED_PROVIDER=offline. settings/production.py
refuses it. It is not a model: it follows the shapes the app expects closely enough
for the whole flow (search, a cited answer, streaming, suggestions) to run in a browser.
"""

import json
import re
import time

from rag.llm.base import Generation, Provider, StreamEnd, Usage
from rag.llm.fake import hashed_embedding

_MESSAGE = re.compile(r'<message>(.*?)</message>', re.S)
_FIRST_SOURCE = re.compile(r'<source n="1"[^>]*>\n(.*?)\n</source>', re.S)
_QUESTION_LINE = re.compile(r'^Question: (.+)$', re.M)
ANSWER_WORDS = 40
NOT_FOUND = ("I couldn't find this in the official documents available to me. Please check "
             "the official TIET website or the relevant office.")
SUGGESTIONS = ['What are the hostel fee payment deadlines?', 'Is the mess fee included?',
               'How do I apply for a hostel room?']


def _default(schema):
    """The smallest value that fits a JSON schema (first enum value, empty otherwise)."""
    if 'enum' in schema:
        return schema['enum'][0]
    kind = schema.get('type')
    if kind == 'object':
        return {name: _default(sub) for name, sub in schema.get('properties', {}).items()}
    return {'array': [], 'string': '', 'boolean': False, 'integer': 0, 'number': 0}.get(kind)


def _structured(request):
    schema = request.json_schema
    properties = schema.get('properties', {})
    data = _default(schema)
    if 'standalone_query' in properties:  # query analysis: always a college question
        match = _MESSAGE.search(request.prompt)
        question = ' '.join((match.group(1) if match else request.prompt).split())
        data.update(standalone_query=question, keywords=question, language='english')
    elif 'suggestions' in properties:
        data['suggestions'] = SUGGESTIONS
    return data


def _answer(prompt):
    match = _FIRST_SOURCE.search(prompt)
    if not match:
        return NOT_FOUND
    words = match.group(1).split()[:ANSWER_WORDS]
    return f'{" ".join(words).rstrip(".,;:")} [1].'


def _plain(prompt):
    match = _QUESTION_LINE.search(prompt)
    if match:  # the chat title prompt
        return ' '.join(match.group(1).split()[:6])
    return 'Offline summary.'


class OfflineProvider(Provider):
    name = 'offline'

    def __init__(self, delay_ms=60):
        self.delay = max(0, delay_ms) / 1000

    def embed(self, texts, *, model, dimensions, task, titles=None):
        return [hashed_embedding(text, dimensions) for text in texts]

    def generate(self, request):
        if request.json_schema:
            text = json.dumps(_structured(request))
        else:
            text = _plain(request.prompt)
        return Generation(text=text, model=request.model, usage=Usage(calls=1))

    def stream(self, request):
        text = _answer(request.prompt)
        for word in re.findall(r'\S+\s*', text):
            if self.delay:
                time.sleep(self.delay)
            yield word
        yield StreamEnd(Generation(text=text, model=request.model, usage=Usage(calls=1)))

    def read_pdf(self, *, model, pdf, prompt, max_output_tokens):
        return Generation(text='# Document\n\nScanned pages are not read offline.', model=model,
                          usage=Usage(calls=1))
