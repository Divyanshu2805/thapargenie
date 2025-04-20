import time

from common.mixins import TimestampedModel, UUIDModel, choices_check, max_length_check
from django.conf import settings
from django.db import models
from django.utils import timezone
from knowledge.models import Category

MAX_QUESTION_CHARS = 2000
MAX_MESSAGE_CHARS = 20_000
MAX_MESSAGES_PER_CONVERSATION = 200


class ConversationQuerySet(models.QuerySet):
    def owned_by(self, user):
        """The only way views should reach conversations: always scoped to one user."""
        return self.filter(user=user)


class TitleSource(models.TextChoices):
    AUTO = 'auto', 'Automatic'
    USER = 'user', 'Set by user'


class Conversation(UUIDModel, TimestampedModel):
    TitleSource = TitleSource

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations'
    )
    title = models.CharField(max_length=120, blank=True)
    title_source = models.CharField(
        max_length=8, choices=TitleSource.choices, default=TitleSource.AUTO
    )
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(default=timezone.now)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ('-last_message_at',)
        indexes = [
            models.Index(fields=('user', '-last_message_at'), name='conversation_sidebar_idx'),
        ]
        constraints = [
            choices_check('title_source', TitleSource, 'conversation_title_source_valid'),
        ]

    def __str__(self):
        return self.title or str(self.pk)


class Role(models.TextChoices):
    USER = 'user', 'User'
    ASSISTANT = 'assistant', 'Assistant'


class Status(models.TextChoices):
    COMPLETE = 'complete', 'Complete'
    STREAMING = 'streaming', 'Streaming'
    STOPPED = 'stopped', 'Stopped'
    FAILED = 'failed', 'Failed'


class AnswerType(models.TextChoices):
    ANSWERED = 'answered', 'Answered'
    NO_ANSWER = 'no_answer', 'Not found'
    ERROR = 'error', 'Error'


class Message(UUIDModel, TimestampedModel):
    Role = Role

    Status = Status

    AnswerType = AnswerType

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETE)
    # NULL (not '') means "not applicable": user messages never have one (DB-checked).
    answer_type = models.CharField(  # noqa: DJ001
        max_length=16, choices=AnswerType.choices, null=True, blank=True
    )
    model = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    client_request_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ('created_at',)
        indexes = [
            models.Index(fields=('conversation', 'created_at'), name='message_conversation_idx'),
        ]
        constraints = [
            choices_check('role', Role, 'message_role_valid'),
            choices_check('status', Status, 'message_status_valid'),
            choices_check('answer_type', AnswerType, 'message_answer_type_valid',
                          allow_null=True),
            max_length_check('content', MAX_MESSAGE_CHARS, 'message_content_length'),
            models.CheckConstraint(
                condition=~models.Q(role='user') | models.Q(answer_type__isnull=True),
                name='message_user_has_no_answer_type',
            ),
            models.UniqueConstraint(
                fields=('conversation', 'client_request_id'),
                condition=models.Q(client_request_id__isnull=False),
                name='message_idempotency_key',
            ),
        ]

    def __str__(self):
        return f'{self.role}:{self.pk}'


class MessageSource(UUIDModel):
    """A citation snapshot: stays readable after the document it came from is gone."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='sources')
    position = models.PositiveSmallIntegerField()
    chunk = models.ForeignKey(
        'knowledge.Chunk', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    document = models.ForeignKey(
        'knowledge.Document', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    title = models.CharField(max_length=300)
    url = models.URLField(max_length=2000, blank=True)
    heading_path = models.CharField(max_length=500, blank=True)
    snippet = models.CharField(max_length=600, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices, blank=True)
    academic_year = models.CharField(max_length=7, blank=True)
    page_start = models.PositiveIntegerField(null=True, blank=True)
    page_end = models.PositiveIntegerField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    cited = models.BooleanField(default=False)

    class Meta:
        ordering = ('position',)
        indexes = [models.Index(fields=('document',), name='source_document_idx')]
        constraints = [
            models.UniqueConstraint(fields=('message', 'position'), name='source_unique_position')
        ]


class Reason(models.TextChoices):
    INCORRECT = 'incorrect', 'Incorrect'
    OUTDATED = 'outdated', 'Outdated'
    INCOMPLETE = 'incomplete', 'Incomplete'
    IRRELEVANT = 'irrelevant', 'Irrelevant'
    UNCLEAR = 'unclear', 'Unclear'
    OTHER = 'other', 'Other'


class Feedback(UUIDModel, TimestampedModel):
    Reason = Reason

    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='feedback')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedback'
    )
    rating = models.SmallIntegerField()
    # NULL means no reason given (thumbs-up never has one).
    reason = models.CharField(  # noqa: DJ001
        max_length=16, choices=Reason.choices, null=True, blank=True
    )
    comment = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(rating__in=(-1, 1)),
                                   name='feedback_rating_valid'),
            choices_check('reason', Reason, 'feedback_reason_valid', allow_null=True),
        ]


class UsageDaily(models.Model):
    """Content-free counters for quotas and stats. Survives chat deletion."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    day = models.DateField(db_index=True)
    questions = models.PositiveIntegerField(default=0)
    answers = models.PositiveIntegerField(default=0)
    llm_calls = models.PositiveIntegerField(default=0)
    prompt_tokens = models.BigIntegerField(default=0)
    completion_tokens = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('user', 'day'), name='usage_user_day_unique')
        ]

    def __str__(self):
        return f'{self.user_id}:{self.day}'


def default_starter_questions():
    return [
        {'category': 'Fees', 'text': 'What is the BE fee per semester for 2026-27?'},
        {'category': 'Hostels', 'text': 'What are the hostel and mess fees this year?'},
        {'category': 'Admissions',
         'text': 'What were the JEE Main cutoffs for Computer Engineering?'},
        {'category': 'Calendar', 'text': 'When do the mid-semester tests start this semester?'},
        {'category': 'Syllabus', 'text': 'What is covered in UCS301 Data Structures?'},
        {'category': 'Rules', 'text': 'What does the anti-ragging policy require?'},
    ]


class ChatSettings(models.Model):
    """Runtime knobs admins change without a deploy. Exactly one row (id=1)."""

    CACHE_SECONDS = 60

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    daily_question_limit = models.PositiveIntegerField(default=40)
    global_daily_llm_calls = models.PositiveIntegerField(default=5000)
    auto_title_enabled = models.BooleanField(default=True)
    starter_questions = models.JSONField(default=default_starter_questions)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    _cached = None
    _cached_at = 0.0

    class Meta:
        verbose_name_plural = 'chat settings'
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name='chat_settings_singleton')
        ]

    def __str__(self):
        return 'Chat settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        type(self).forget()

    @classmethod
    def load(cls, *, fresh=False):
        now = time.monotonic()
        if fresh or cls._cached is None or now - cls._cached_at > cls.CACHE_SECONDS:
            cls._cached, _ = cls.objects.get_or_create(pk=1)
            cls._cached_at = now
        return cls._cached

    @classmethod
    def forget(cls):
        cls._cached = None
