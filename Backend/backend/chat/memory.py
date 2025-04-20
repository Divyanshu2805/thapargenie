"""Background upkeep for a conversation: a short title from its first question."""

import logging

from common.text import truncate
from rag.llm import BadResponse, LLMError, get_llm

from chat import quota
from chat.models import Conversation

logger = logging.getLogger(__name__)

TITLE_PROMPT = """Write a short title (max 6 words) for a student's chat that starts with this \
question. Use the student's language. No quotes, no trailing punctuation.

Question: {question}"""


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
