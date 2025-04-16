"""Question -> streamed, cited answer. Pure logic: no persistence, no HTTP.

`answer_events()` yields (event, data) pairs that map one-to-one onto the SSE events:
status, sources, delta, done. The chat layer stores the final result; `manage.py ask`
just prints it.
"""

import re
from dataclasses import dataclass, field

from rag import prompt
from rag.context import build_sources
from rag.llm import StreamEnd, get_llm
from rag.retrieve import retrieve

KEEP = 8
HISTORY_MESSAGES = 4
HISTORY_CHARS = 1200

NOT_FOUND_OPENING = "i couldn't find"
NOT_FOUND = (
    "I couldn't find this in the official TIET documents I have access to. Please check "
    'the official website (https://www.thapar.edu) or contact the relevant office directly.'
)

_CITATION = re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]')


class AnswerType:
    ANSWERED = 'answered'
    NO_ANSWER = 'no_answer'


@dataclass
class AnswerResult:
    text: str
    answer_type: str
    question: str
    sources: list = field(default_factory=list)
    cited: list = field(default_factory=list)
    model: str = ''


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


def answer_events(question, *, llm=None, history=(), profile=None, today=None):
    llm = llm or get_llm()

    yield 'status', {'stage': 'searching'}
    retrieval = retrieve(llm, question)
    sources = build_sources(retrieval.candidates[:KEEP])
    yield 'sources', {'sources': [source.public() for source in sources]}

    if not sources:
        yield 'delta', {'text': NOT_FOUND}
        yield 'done', AnswerResult(text=NOT_FOUND, answer_type=AnswerType.NO_ANSWER,
                                   question=question)
        return

    yield 'status', {'stage': 'writing', 'detail': f'Reading {len(sources)} sources'}
    parts, model = [], ''
    for item in llm.stream(
        prompt.answer_prompt(question, sources, profile=profile, today=today),
        system=prompt.SYSTEM,
        history=_history_messages(history),
        temperature=0.2,
        max_output_tokens=2048,
    ):
        if isinstance(item, StreamEnd):
            model = item.generation.model
        else:
            parts.append(item)
            yield 'delta', {'text': item}

    text = ''.join(parts).strip()
    cited = cited_numbers(text, len(sources))
    # A "not found" reply may still cite a related source; it is still not an answer.
    not_found = text.lower().replace('’', "'").startswith(NOT_FOUND_OPENING)
    answer_type = AnswerType.ANSWERED if cited and not not_found else AnswerType.NO_ANSWER
    yield 'done', AnswerResult(
        text=text,
        answer_type=answer_type,
        question=question,
        sources=sources,
        cited=cited,
        model=model,
    )


def answer(question, **options):
    """Run the whole pipeline and return only the final AnswerResult."""
    result = None
    for event, data in answer_events(question, **options):
        if event == 'done':
            result = data
    return result
