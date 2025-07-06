"""Background upkeep for a conversation: a short title and a rolling summary.

The answer model sees the last few messages verbatim. Older turns are compressed into a
summary of durable facts (programme, year, hostel, what was already answered) so long
chats keep their context without growing the prompt.
"""

import logging

from common.text import truncate
from django.db import transaction
from rag.llm import BadResponse, LLMError, get_llm

from chat import quota
from chat.engine import active_path, history
from chat.models import MAX_SUMMARY_CHARS, Conversation

logger = logging.getLogger(__name__)

# Summarise once more than this many path messages are outside the summary.
SUMMARY_AFTER = 10
# Messages the answer prompt keeps verbatim (pipeline.HISTORY_MESSAGES) stay out of it.
KEEP_VERBATIM = 4

TITLE_PROMPT = """Write a short title (max 6 words) for a student's chat that starts with this \
question. Use the student's language. No quotes, no trailing punctuation.

Question: {question}"""

SUMMARY_PROMPT = """Summarise the conversation between a Thapar Institute student and the \
help assistant below in at most 120 words. Keep only durable facts useful for later \
questions: the student's programme, year, campus, hostel, what they asked and the key \
answers (with years/amounts exactly as written). No greetings, no advice.

{previous}{transcript}"""


def make_title(conversation_id, question):
    conversation = Conversation.objects.filter(pk=conversation_id).select_related('user').first()
    if conversation is None or conversation.title_source != Conversation.TitleSource.AUTO:
        return
    llm = get_llm()
    try:
        result = llm.generate(
            TITLE_PROMPT.format(question=question[:500]), fast=True, temperature=0.3,
            max_output_tokens=40,
        )
    except (LLMError, BadResponse) as error:
        logger.info('Title generation skipped: %s', error)
        return
    finally:
        quota.record_calls(conversation.user, llm.usage)
    title = truncate(' '.join(result.text.strip().strip('"\'').split()), 120)
    if title:
        Conversation.objects.filter(
            pk=conversation_id, title_source=Conversation.TitleSource.AUTO
        ).update(title=title)


def update_summary(conversation_id):
    conversation = Conversation.objects.filter(pk=conversation_id).select_related('user').first()
    if conversation is None:
        return
    path, _ = active_path(conversation)
    ids = [message.pk for message in path]
    start = ids.index(conversation.memory_upto_id) + 1 if conversation.memory_upto_id in ids \
        else 0
    older = path[start:-KEEP_VERBATIM] if len(path) > KEEP_VERBATIM else []
    if len(path) - start <= SUMMARY_AFTER or not older:
        return
    transcript = '\n'.join(
        f'{"Student" if m["role"] == "user" else "Assistant"}: {truncate(m["content"], 600)}'
        for m in history(older)
    )
    previous = ''
    if conversation.memory_upto_id in ids and conversation.memory_summary:
        previous = f'Summary so far: {conversation.memory_summary}\n\nNew messages:\n'
    llm = get_llm()
    try:
        result = llm.generate(
            SUMMARY_PROMPT.format(previous=previous, transcript=transcript),
            fast=True, temperature=0, max_output_tokens=400,
        )
    except (LLMError, BadResponse) as error:
        logger.info('Summary skipped: %s', error)
        return
    finally:
        quota.record_calls(conversation.user, llm.usage)
    with transaction.atomic():
        Conversation.objects.filter(pk=conversation_id).update(
            memory_summary=truncate(result.text.strip(), MAX_SUMMARY_CHARS),
            memory_upto=older[-1],
        )
