"""Follow-up question suggestions, generated only when a student asks for them.

One fast-model call per answer at most: the result is saved on the message, so asking
again (or reloading) is free. The model sees the question, the answer and the cited
source titles; never who the student is.
"""

import logging

from common.text import truncate
from rag.llm import BadResponse, LLMError, get_llm

from chat import quota
from chat.errors import Maintenance, ServiceBusy, SuggestionsFailed, SuggestionsUnavailable
from chat.models import ChatSettings, Message

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 3
MAX_CHARS = 150
ELIGIBLE = (Message.AnswerType.ANSWERED, Message.AnswerType.CACHED)

SCHEMA = {
    'type': 'object',
    'properties': {
        'suggestions': {
            'type': 'array',
            'items': {'type': 'string'},
            'maxItems': MAX_SUGGESTIONS,
        },
    },
    'required': ['suggestions'],
}

PROMPT = """A Thapar Institute (TIET) student asked the help assistant a question and got \
the answer below. Suggest up to {count} short follow-up questions the student would \
plausibly ask next about the same topic.

Rules:
- Each is a question of at most 100 characters, in the same language and style as the \
student's question (English or Hinglish).
- Each makes sense on its own: name the programme, year, hostel or document instead of \
saying "it" or "that".
- Stay on official institute information (fees, admissions, hostels, calendar, courses, \
rules, departments, placements, contacts). Never ask about the student's own grades, \
attendance, dues or other personal records.
- Don't repeat the student's question or ask something the answer already fully covers.

Student's question: {question}

Answer: {answer}

Sources the answer used: {sources}"""


def clean(items, question=''):
    """Strings only, whitespace collapsed, no empties or repeats (nor the question itself)."""
    seen = {' '.join(question.split()).casefold()}
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, str):
            continue
        text = truncate(' '.join(item.split()), MAX_CHARS)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
        if len(out) == MAX_SUGGESTIONS:
            break
    return out


def suggest(message, user):
    """Return (and save) follow-ups for one of `user`'s answers."""
    if (message.role != Message.Role.ASSISTANT or message.status != Message.Status.COMPLETE
            or message.answer_type not in ELIGIBLE or message.parent_id is None):
        raise SuggestionsUnavailable()
    if message.suggestions:
        return message.suggestions

    settings = ChatSettings.load()
    if settings.maintenance_mode and not user.is_staff:
        raise Maintenance(settings.maintenance_message or None)
    if quota.global_calls_today() >= settings.global_daily_llm_calls:
        raise ServiceBusy()

    question = message.parent.content
    titles = list(message.sources.filter(cited=True).order_by('position')
                  .values_list('title', flat=True)[:5])
    prompt = PROMPT.format(
        count=MAX_SUGGESTIONS,
        question=truncate(question, 500),
        answer=truncate(message.content, 2000),
        sources='; '.join(titles) or 'none',
    )
    llm = get_llm()
    try:
        data = llm.generate_json(prompt, json_schema=SCHEMA, fast=True, temperature=0.4,
                                 max_output_tokens=300)
    except (LLMError, BadResponse) as error:
        logger.warning('Follow-up suggestions failed: %s', error)
        raise SuggestionsFailed() from error
    finally:
        quota.record_calls(user, llm.usage)

    suggestions = clean(data.get('suggestions') if isinstance(data, dict) else None, question)
    if suggestions:
        # Only fill an empty list: a concurrent request may have saved one already.
        Message.objects.filter(pk=message.pk, suggestions=[]).update(suggestions=suggestions)
    return suggestions
