"""One question-and-answer turn: admission checks, persistence and the event stream.

`start_turn()` runs in the request, inside one transaction: it applies every check
(daily quota, global budget, one stream per user, conversation size, idempotency)
and saves the user message plus an empty `streaming` assistant message.
Only then does streaming start, so a question is never lost and a retry with the same
`client_request_id` can never create a duplicate.

`stream_turn()` runs the RAG pipeline and saves the outcome: complete, stopped (the
client disconnected) or failed. Its events are the ones the chat API streams.
"""

import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from common.text import truncate
from django.db import transaction
from django.utils import timezone
from rag.llm import LLMError, QuotaExhausted, get_llm
from rag.pipeline import answer_events

from chat import background, memory, quota
from chat.errors import (
    ConversationBusy,
    ConversationFull,
    DailyQuotaExceeded,
    ServiceBusy,
)
from chat.models import (
    MAX_MESSAGES_PER_CONVERSATION,
    ChatSettings,
    Conversation,
    Message,
    MessageSource,
)
from chat.serializers import message_payload, source_payload

logger = logging.getLogger(__name__)

BUSY_WINDOW = timedelta(minutes=2)


@dataclass
class Turn:
    conversation: Conversation
    user_message: Message
    assistant_message: Message
    replay: bool = False
    remaining_today: int | None = None


def _check_admission(user, settings):
    usage = quota.usage_row(user, lock=True)  # serialises concurrent sends per user
    if not user.is_staff and usage.questions >= settings.daily_question_limit:
        raise DailyQuotaExceeded()
    if quota.global_calls_today() >= settings.global_daily_llm_calls:
        raise ServiceBusy()
    # Streams older than BUSY_WINDOW are abandoned (crash, restart) and do not block.
    busy = Message.objects.filter(
        conversation__user=user,
        status=Message.Status.STREAMING,
        updated_at__gte=timezone.now() - BUSY_WINDOW,
    ).exists()
    if busy:
        raise ConversationBusy()
    return usage


def _replay(conversation, client_request_id):
    """An earlier request with the same key: hand back what it produced."""
    existing = Message.objects.filter(
        conversation=conversation, client_request_id=client_request_id
    ).first()
    if existing is None:
        return None
    if existing.role == Message.Role.USER:
        assistant = existing.children.order_by('-created_at').first()
        user_message = existing
    else:
        assistant, user_message = existing, existing.parent
    if assistant is None or assistant.status == Message.Status.STREAMING:
        raise ConversationBusy()
    return Turn(conversation, user_message, assistant, replay=True)


@transaction.atomic
def start_turn(user, conversation, *, content, client_request_id):
    conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
    replay = _replay(conversation, client_request_id)
    if replay is not None:
        return replay

    settings = ChatSettings.load()
    usage = _check_admission(user, settings)
    new_messages = 2
    if conversation.message_count + new_messages > MAX_MESSAGES_PER_CONVERSATION:
        raise ConversationFull()

    now = timezone.now()
    parent = conversation.messages.filter(role=Message.Role.ASSISTANT).last()
    user_message = Message.objects.create(
        conversation=conversation, parent=parent, role=Message.Role.USER,
        content=content, client_request_id=client_request_id,
    )
    assistant = Message.objects.create(
        conversation=conversation, parent=user_message, role=Message.Role.ASSISTANT,
        status=Message.Status.STREAMING,
    )

    conversation.message_count += new_messages
    conversation.last_message_at = now
    if not conversation.title:
        conversation.title = truncate(' '.join(user_message.content.split()), 80)
    conversation.save()
    usage.questions += 1
    usage.save(update_fields=['questions'])
    return Turn(
        conversation, user_message, assistant,
        remaining_today=quota.remaining_from(user, usage, settings),
    )


def _history(messages):
    """Earlier turns the model should see (oldest first); failed answers are skipped."""
    usable = []
    for message in messages:
        if message.role == Message.Role.USER:
            usable.append({'role': 'user', 'content': message.content})
        elif message.status in (Message.Status.COMPLETE, Message.Status.STOPPED) and \
                message.content:
            usable.append({'role': 'assistant', 'content': message.content})
    return usable


def _profile(user):
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    return {
        'campus': profile.campus,
        'program': profile.program,
        'year of study': profile.academic_year,
    }


def _source_rows(result):
    rows = []
    for source in result.sources:
        rows.append({
            **source.public(),
            'chunk_id': source.chunk_ids[0] if source.chunk_ids else None,
            'document_id': source.document_id,
            'cited': source.number in result.cited,
            'score': source.score,
        })
    return rows


def _save_sources(message, result):
    rows = _source_rows(result)
    MessageSource.objects.bulk_create([
        MessageSource(
            message=message,
            position=row['position'],
            chunk_id=row.get('chunk_id'),
            document_id=row.get('document_id'),
            title=(row.get('title') or '')[:300],
            url=row.get('url') or '',
            heading_path=(row.get('heading_path') or '')[:500],
            snippet=(row.get('snippet') or '')[:600],
            category=row.get('category') or '',
            academic_year=row.get('academic_year') or '',
            page_start=row.get('page_start'),
            page_end=row.get('page_end'),
            score=row.get('score'),
            cited=bool(row.get('cited')),
        )
        for row in rows
    ])


def _finish(turn, result, llm, started):
    message = turn.assistant_message
    with transaction.atomic():
        message.content = result.text
        message.status = Message.Status.COMPLETE
        message.answer_type = result.answer_type
        message.model = result.model
        message.prompt_tokens = llm.usage.prompt_tokens or None
        message.completion_tokens = llm.usage.completion_tokens or None
        message.latency_ms = int((time.monotonic() - started) * 1000)
        message.save()
        _save_sources(message, result)
    quota.record_answer(turn.conversation.user, llm.usage)


def _after_answer(turn, result, first_turn):
    settings = ChatSettings.load()
    conversation = turn.conversation
    if first_turn and settings.auto_title_enabled and \
            conversation.title_source == Conversation.TitleSource.AUTO:
        background.submit(memory.make_title, conversation.pk, turn.user_message.content)


def _fail(turn, code, partial=''):
    Message.objects.filter(pk=turn.assistant_message.pk).update(
        status=Message.Status.FAILED if not partial else Message.Status.STOPPED,
        content=partial,
        answer_type=Message.AnswerType.ERROR if not partial else None,
        error_code=code,
        updated_at=timezone.now(),
    )


def replay_events(turn):
    message = turn.assistant_message
    yield 'meta', _meta(turn)
    sources = [source_payload(s) for s in message.sources.select_related('document')]
    yield 'sources', {'sources': sources}
    if message.content:
        yield 'delta', {'text': message.content}
    yield 'done', {'message': message_payload(message)}


def _meta(turn):
    return {
        'conversation_id': str(turn.conversation.pk),
        'user_message_id': str(turn.user_message.pk),
        'assistant_message_id': str(turn.assistant_message.pk),
        'remaining_today': turn.remaining_today if not turn.replay
        else quota.remaining(turn.conversation.user),
    }


def stream_turn(turn):
    """Yield (event, data) for a started turn, persisting the outcome."""
    if turn.replay:
        yield from replay_events(turn)
        return

    user = turn.conversation.user
    prior = list(turn.conversation.messages.filter(
        created_at__lt=turn.user_message.created_at
    ))
    llm = get_llm()
    started = time.monotonic()
    parts = []
    finished = False

    yield 'meta', _meta(turn)
    try:
        events = answer_events(
            turn.user_message.content,
            llm=llm,
            history=_history(prior),
            profile=_profile(user),
        )
        for event, data in events:
            if event == 'delta':
                parts.append(data['text'])
            if event == 'done':
                _finish(turn, data, llm, started)
                finished = True
                # Before the final yield: a client that disconnects right after `done`
                # must not skip caching, titling or memory.
                _after_answer(turn, data, first_turn=not prior)
                turn.assistant_message.refresh_from_db()
                yield 'done', {
                    'message': message_payload(turn.assistant_message),
                    'remaining_today': quota.remaining(user),
                }
                return
            if event == 'sources':
                # Sources get ids once saved; before that the client shows positions.
                data = {'sources': data['sources']}
            yield event, data
    except GeneratorExit:
        # The client went away (stop button, closed tab): keep what was written.
        if not finished:
            _fail(turn, 'stopped', partial=''.join(parts))
            quota.record_calls(user, llm.usage)
        raise
    except QuotaExhausted:
        _fail(turn, 'llm_quota')
        quota.record_calls(user, llm.usage)
        yield 'error', {'code': 'service_busy', 'message': ServiceBusy.default_detail,
                        'retryable': True}
    except LLMError:
        logger.warning('LLM failure for message %s', turn.assistant_message.pk, exc_info=True)
        _fail(turn, 'llm_unavailable')
        quota.record_calls(user, llm.usage)
        yield 'error', {'code': 'llm_unavailable',
                        'message': 'The answer service is unavailable. Please retry.',
                        'retryable': True}
    except Exception:
        logger.exception('Answer failed for message %s', turn.assistant_message.pk)
        _fail(turn, 'internal_error')
        quota.record_calls(user, llm.usage)
        yield 'error', {'code': 'internal_error',
                        'message': 'Something went wrong. Please retry.', 'retryable': True}
