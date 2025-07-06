"""Per-user daily question limit, global LLM budget and usage counters."""

from django.db.models import F, Sum
from django.utils import timezone

from chat.models import ChatSettings, UsageDaily


def today():
    return timezone.localdate()


def usage_row(user, *, lock=False):
    rows = UsageDaily.objects.select_for_update() if lock else UsageDaily.objects
    row, _ = rows.get_or_create(user=user, day=today())
    return row


def remaining_from(user, usage, settings):
    if user.is_staff:
        return None
    return max(0, settings.daily_question_limit - usage.questions)


def remaining(user):
    if user.is_staff:
        return None
    limit = ChatSettings.load().daily_question_limit
    used = UsageDaily.objects.filter(user=user, day=today()).values_list('questions', flat=True)
    return max(0, limit - (used[0] if used else 0))


def global_calls_today():
    return UsageDaily.objects.filter(day=today()).aggregate(total=Sum('llm_calls'))['total'] or 0


def record_answer(user, usage, *, cached=False):
    UsageDaily.objects.filter(user=user, day=today()).update(
        answers=F('answers') + 1,
        cached=F('cached') + (1 if cached else 0),
        llm_calls=F('llm_calls') + usage.calls,
        prompt_tokens=F('prompt_tokens') + usage.prompt_tokens,
        completion_tokens=F('completion_tokens') + usage.completion_tokens,
    )


def record_calls(user, usage):
    """LLM calls made outside a counted answer (failed/stopped turns, titles, memory)."""
    if usage.calls:
        usage_row(user)
        UsageDaily.objects.filter(user=user, day=today()).update(
            llm_calls=F('llm_calls') + usage.calls,
            prompt_tokens=F('prompt_tokens') + usage.prompt_tokens,
            completion_tokens=F('completion_tokens') + usage.completion_tokens,
        )
