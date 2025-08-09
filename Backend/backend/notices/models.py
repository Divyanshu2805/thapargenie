from common.mixins import TimestampedModel, UUIDModel, choices_check, max_length_check
from django.conf import settings
from django.db import models
from django.utils import timezone
from knowledge.models import Category

MAX_TITLE_CHARS = 160
MAX_BODY_CHARS = 5000


class Importance(models.TextChoices):
    NORMAL = 'normal', 'Normal'
    IMPORTANT = 'important', 'Important'


class State(models.TextChoices):
    """Derived from the dates and the draft flag; not stored."""

    PUBLISHED = 'published', 'Published'
    SCHEDULED = 'scheduled', 'Scheduled'
    DRAFT = 'draft', 'Draft'
    EXPIRED = 'expired', 'Expired'


class NoticeQuerySet(models.QuerySet):
    def visible(self, now=None):
        """What students see: published, and not yet expired."""
        now = now or timezone.now()
        return self.filter(is_draft=False, publish_at__lte=now).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )

    def in_state(self, state, now=None):
        now = now or timezone.now()
        if state == State.DRAFT:
            return self.filter(is_draft=True)
        if state == State.SCHEDULED:
            return self.filter(is_draft=False, publish_at__gt=now)
        if state == State.EXPIRED:
            return self.filter(is_draft=False, expires_at__lte=now)
        return self.visible(now)


class Notice(UUIDModel, TimestampedModel):
    """An announcement posted by an admin."""

    Importance = Importance
    State = State

    title = models.CharField(max_length=MAX_TITLE_CHARS)
    body = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=Category.choices,
                                default=Category.NOTICES)
    importance = models.CharField(max_length=10, choices=Importance.choices,
                                  default=Importance.NORMAL)
    is_pinned = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    publish_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    link_url = models.URLField(max_length=2000, blank=True)
    # "ThaparGenie can answer from this": keep a knowledge-base copy while published.
    answerable = models.BooleanField(default=True)
    document = models.ForeignKey(
        'knowledge.Document', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='notices',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    objects = NoticeQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=('is_draft', 'publish_at'), name='notice_publish_idx'),
            models.Index(fields=('is_pinned', 'publish_at'), name='notice_pinned_idx'),
        ]
        constraints = [
            choices_check('category', Category, 'notice_category_valid'),
            choices_check('importance', Importance, 'notice_importance_valid'),
            max_length_check('body', MAX_BODY_CHARS, 'notice_body_length'),
            models.CheckConstraint(
                condition=models.Q(link_url='') | models.Q(link_url__startswith='https://'),
                name='notice_link_url_https',
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__isnull=True)
                | models.Q(expires_at__gt=models.F('publish_at')),
                name='notice_expires_after_publish',
                violation_error_message='The expiry must be after the publish time.',
            ),
        ]

    def __str__(self):
        return self.title

    def state(self, now=None):
        now = now or timezone.now()
        if self.is_draft:
            return State.DRAFT
        if self.publish_at > now:
            return State.SCHEDULED
        if self.expires_at and self.expires_at <= now:
            return State.EXPIRED
        return State.PUBLISHED
