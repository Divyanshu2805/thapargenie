"""Question -> streamed, cited answer. Pure logic: no persistence, no HTTP.

`answer_events()` yields (event, data) pairs that map one-to-one onto the SSE events:
status, sources, delta, done. The chat layer stores the final result; `manage.py ask`
just prints it.
"""

import re
import time
from dataclasses import dataclass, field

from rag import prompt
from rag.analysis import Intent, QueryAnalysis, analyze
from rag.context import build_sources
from rag.llm import StreamEnd, get_llm
from rag.rerank import KEEP, rerank
from rag.retrieve import KeywordSearch, retrieve

HISTORY_MESSAGES = 4
HISTORY_CHARS = 1200

CANNED = {
    Intent.GREETING: (
        "Hi! I'm ThaparGenie. Ask me anything about Thapar Institute: admissions, fees and "
        'scholarships, hostels, the academic calendar, courses and syllabus, rules, '
        'departments, faculty or placements.'
    ),
    Intent.PERSONAL_RECORD: (
        "I can't see personal records such as your marks, attendance, results or fee dues. "
        'Please check them on Webkiosk (https://webkiosk.thapar.edu), or contact the '
        'relevant office if something looks wrong.'
    ),
    Intent.OUT_OF_SCOPE: (
        'I can only help with questions about Thapar Institute of Engineering and '
        'Technology: admissions, fees, hostels, academics, rules and campus life. '
        'Is there something about TIET I can help you with?'
    ),
}

NOT_FOUND_OPENING = "i couldn't find"
NOT_FOUND = (
    "I couldn't find this in the official TIET documents I have access to. Please check "
    'the official website (https://www.thapar.edu) or contact the relevant office directly.'
)


_CITATION = re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]')


class AnswerType:
    ANSWERED = 'answered'
    NO_ANSWER = 'no_answer'
    SMALLTALK = 'smalltalk'
    OUT_OF_SCOPE = 'out_of_scope'
    PERSONAL_RECORD = 'personal_record'


_INTENT_TYPES = {
    Intent.GREETING: AnswerType.SMALLTALK,
    Intent.OUT_OF_SCOPE: AnswerType.OUT_OF_SCOPE,
    Intent.PERSONAL_RECORD: AnswerType.PERSONAL_RECORD,
}


@dataclass
class AnswerResult:
    text: str
    answer_type: str
    analysis: QueryAnalysis
    sources: list = field(default_factory=list)
    cited: list = field(default_factory=list)
    model: str = ''
    reranked: bool = False
    retrieval_trace: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)


class _Timer:
    def __init__(self):
        self.timings = {}
        self._start = time.monotonic()
        self._last = self._start

    def lap(self, name):
        now = time.monotonic()
        self.timings[name] = round((now - self._last) * 1000)
        self._last = now

    def mark(self, name):
        """Record the time since the start (not a lap), e.g. the first answer word."""
        self.timings.setdefault(name, round((time.monotonic() - self._start) * 1000))

    def total(self):
        self.timings['total'] = round((time.monotonic() - self._start) * 1000)
        return self.timings


def cited_numbers(answer, max_source):
    """Source numbers cited as [n] or [n, m], in order of first use."""
    numbers = []
    for group in _CITATION.findall(answer):
        for part in group.split(','):
            number = int(part)
            if 1 <= number <= max_source and number not in numbers:
                numbers.append(number)
    return numbers


def _history_messages(history):
    messages = []
    for message in list(history)[-HISTORY_MESSAGES:]:
        content = message['content']
        if message['role'] == 'assistant' and len(content) > HISTORY_CHARS:
            content = content[:HISTORY_CHARS] + ' …'
        messages.append({'role': message['role'], 'content': content})
    return messages


def answer_events(
    question,
    *,
    llm=None,
    history=(),
    profile=None,
    rerank_enabled=False,
    today=None,
):
    llm = llm or get_llm()
    timer = _Timer()

    yield 'status', {'stage': 'understanding'}
    analysis = analyze(llm, question, history=history, profile=profile, today=today)
    timer.lap('analysis')

    if analysis.intent != Intent.COLLEGE:
        text = CANNED[analysis.intent]
        timer.mark('first_token')
        yield 'delta', {'text': text}
        yield 'done', AnswerResult(
            text=text,
            answer_type=_INTENT_TYPES[analysis.intent],
            analysis=analysis,
            timings=timer.total(),
        )
        return

    yield 'status', {'stage': 'searching'}
    # The keyword search needs no embeddings: it runs while the queries are embedded.
    keywords = KeywordSearch(analysis)
    queries = analysis.search_queries
    vectors = llm.embed_queries(queries)
    timer.lap('embedding')

    retrieval = retrieve(llm, analysis, vectors=vectors, keywords=keywords)
    timer.lap('retrieval')

    candidates, reranked = retrieval.candidates[:KEEP], False
    if rerank_enabled and retrieval.candidates:
        detail = f'Checking {len(retrieval.candidates)} passages'
        yield 'status', {'stage': 'reading', 'detail': detail}
        candidates, reranked = rerank(llm, analysis.standalone_query, retrieval.candidates)
        timer.lap('rerank')

    sources = build_sources(candidates)
    timer.lap('context')
    yield 'sources', {'sources': [source.public() for source in sources]}

    if not sources:
        timer.mark('first_token')
        yield 'delta', {'text': NOT_FOUND}
        yield 'done', AnswerResult(
            text=NOT_FOUND,
            answer_type=AnswerType.NO_ANSWER,
            analysis=analysis,
            reranked=reranked,
            retrieval_trace=retrieval.trace(),
            timings=timer.total(),
        )
        return

    yield 'status', {'stage': 'writing', 'detail': f'Reading {len(sources)} sources'}
    parts, model = [], ''
    for item in llm.stream(
        prompt.answer_prompt(analysis, sources, profile=profile, today=today),
        system=prompt.SYSTEM,
        history=_history_messages(history),
        temperature=0.2,
        max_output_tokens=2048,
    ):
        if isinstance(item, StreamEnd):
            model = item.generation.model
        else:
            timer.mark('first_token')
            parts.append(item)
            yield 'delta', {'text': item}
    timer.lap('generation')

    text = ''.join(parts).strip()
    cited = cited_numbers(text, len(sources))
    # A "not found" reply may still cite a related source; it is still not an answer.
    not_found = text.lower().replace('’', "'").startswith(NOT_FOUND_OPENING)
    answer_type = AnswerType.ANSWERED if cited and not not_found else AnswerType.NO_ANSWER
    yield 'done', AnswerResult(
        text=text,
        answer_type=answer_type,
        analysis=analysis,
        sources=sources,
        cited=cited,
        model=model,
        reranked=reranked,
        retrieval_trace=retrieval.trace(),
        timings=timer.total(),
    )


def answer(question, **options):
    """Run the whole pipeline and return only the final AnswerResult."""
    result = None
    for event, data in answer_events(question, **options):
        if event == 'done':
            result = data
    return result
