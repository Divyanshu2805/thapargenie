import uuid

from django.conf import settings
from django.db import models


class AuditOutcome(models.TextChoices):
    SUCCEEDED = 'succeeded', 'Succeeded'
    DENIED = 'denied', 'Denied'
    FAILED = 'failed', 'Failed'


class AuditActorKind(models.TextChoices):
    USER = 'user', 'User'
    SERVICE = 'service', 'Service'
    ANONYMOUS = 'anonymous', 'Anonymous'


class AuditEvent(models.Model):
    """Metadata-only, append-only security and operational event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    actor_kind = models.CharField(
        max_length=32,
        choices=AuditActorKind.choices,
        default=AuditActorKind.USER,
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=128, blank=True)
    outcome = models.CharField(max_length=16, choices=AuditOutcome.choices)
    request_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('action', 'created_at'), name='audit_action_created_idx'),
            models.Index(
                fields=('resource_type', 'resource_id'),
                name='audit_resource_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome__in=AuditOutcome.values),
                name='audit_outcome_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(actor_kind__in=AuditActorKind.values),
                name='audit_actor_kind_valid',
            ),
        ]

    def __str__(self):
        return f'{self.action}:{self.outcome}'
