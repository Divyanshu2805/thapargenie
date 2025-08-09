import time

from common.mixins import TimestampedModel, UUIDModel, choices_check, max_length_check
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone
from knowledge.models import EMBED_DIMENSIONS, Category
from pgvector.django import HalfVectorField, HnswIndex

MAX_QUESTION_CHARS = 2000
MAX_MESSAGE_CHARS = 20_000
MAX_MESSAGES_PER_CONVERSATION = 200
MAX_SUMMARY_CHARS = 1500


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
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    current_leaf = models.ForeignKey(
        'Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    memory_summary = models.TextField(blank=True)
    memory_upto = models.ForeignKey(
        'Message', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(default=timezone.now)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ('-last_message_at',)
        indexes = [
            models.Index(
                fields=('user', 'is_archived', 'is_pinned', '-last_message_at'),
                name='conversation_sidebar_idx',
            ),
            GinIndex(
                fields=('title',), opclasses=('gin_trgm_ops',), name='conversation_title_trgm'
            ),
        ]
        constraints = [
            choices_check('title_source', TitleSource, 'conversation_title_source_valid'),
            max_length_check('memory_summary', MAX_SUMMARY_CHARS, 'conversation_summary_length'),
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
    SMALLTALK = 'smalltalk', 'Small talk'
    OUT_OF_SCOPE = 'out_of_scope', 'Out of scope'
    PERSONAL_RECORD = 'personal_record', 'Personal record'
    CACHED = 'cached', 'Cached answer'
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
    grounded = models.BooleanField(null=True, blank=True)
    model = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    client_request_id = models.UUIDField(null=True, blank=True)
    # Follow-up questions, generated only when the student asks for them (chat/suggestions.py).
    suggestions = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ('created_at',)
        indexes = [
            models.Index(fields=('conversation', 'created_at'), name='message_conversation_idx'),
            models.Index(
                fields=('answer_type', 'created_at'),
                name='message_answer_type_idx',
                condition=models.Q(role='assistant'),
            ),
            models.Index(fields=('created_at',), name='message_created_idx'),
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


class Review(models.TextChoices):
    OPEN = 'open', 'Open'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'


class Feedback(UUIDModel, TimestampedModel):
    Reason = Reason

    Review = Review

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
    review_status = models.CharField(max_length=10, choices=Review.choices, default=Review.OPEN)
    admin_note = models.CharField(max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=('review_status', 'rating', 'created_at'), name='feedback_review_idx'
            )
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(rating__in=(-1, 1)),
                                   name='feedback_rating_valid'),
            choices_check('reason', Reason, 'feedback_reason_valid', allow_null=True),
            choices_check('review_status', Review, 'feedback_review_valid'),
        ]


class SiteFeedbackKind(models.TextChoices):
    SUGGESTION = 'suggestion', 'Suggestion'
    PROBLEM = 'problem', 'Something isn’t working'
    ANSWERS = 'answers', 'Answer quality'
    OTHER = 'other', 'Other'


MIN_SITE_FEEDBACK_CHARS = 10
MAX_SITE_FEEDBACK_CHARS = 2000


class SiteFeedback(UUIDModel, TimestampedModel):
    """Feedback on ThaparGenie as a whole; `Feedback` is per answer."""

    Kind = SiteFeedbackKind
    Review = Review

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='site_feedback'
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    rating = models.SmallIntegerField(null=True, blank=True)
    message = models.CharField(max_length=MAX_SITE_FEEDBACK_CHARS)
    page = models.CharField(max_length=200, blank=True)
    # Only when this is set may admins see who sent it.
    contact_ok = models.BooleanField(default=False)
    review_status = models.CharField(max_length=10, choices=Review.choices, default=Review.OPEN)
    admin_note = models.CharField(max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=('review_status', 'created_at'), name='sitefeedback_review_idx')
        ]
        constraints = [
            choices_check('kind', SiteFeedbackKind, 'sitefeedback_kind_valid'),
            choices_check('review_status', Review, 'sitefeedback_review_valid'),
            models.CheckConstraint(
                condition=models.Q(rating__isnull=True) | models.Q(rating__gte=1, rating__lte=5),
                name='sitefeedback_rating_valid',
            ),
        ]


class AnswerTrace(models.Model):
    """How an answer was produced. Admin-only, kept for 30 days."""

    message = models.OneToOneField(
        Message, primary_key=True, on_delete=models.CASCADE, related_name='trace'
    )
    standalone_query = models.TextField(blank=True)
    analysis = models.JSONField(default=dict)
    retrieval = models.JSONField(default=dict)
    timings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f'trace:{self.message_id}'


class AnswerCache(UUIDModel):
    """Semantic cache for first-turn questions. Emptied whenever knowledge changes."""

    query_text = models.TextField()
    query_embedding = HalfVectorField(dimensions=EMBED_DIMENSIONS)
    answer = models.TextField()
    sources = models.JSONField(default=list)
    model = models.CharField(max_length=80, blank=True)
    hits = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            HnswIndex(
                fields=('query_embedding',),
                name='answer_cache_hnsw',
                m=16,
                ef_construction=64,
                opclasses=('halfvec_cosine_ops',),
            )
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
    cached = models.PositiveIntegerField(default=0)
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
    # Off by default: on the eval set it added ~2.5 s to time-to-first-token with no
    # quality gain. Admins can switch it on.
    rerank_enabled = models.BooleanField(default=False)
    cache_enabled = models.BooleanField(default=True)
    contextualize_default = models.BooleanField(default=False)
    auto_title_enabled = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    # Off = open access: verified sign-ins are approved automatically.
    require_approval = models.BooleanField(default=True)
    maintenance_message = models.CharField(max_length=300, blank=True)
    banner_text = models.CharField(max_length=300, blank=True)
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
