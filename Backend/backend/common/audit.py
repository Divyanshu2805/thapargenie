"""Audit trail helpers. Every event is metadata only: never question text, answers,
document contents or free-form user input beyond short admin-entered reasons.

Actions are named `<area>.<verb>`, e.g. `document.delete`.
"""

import logging

from api.models import AuditEvent, AuditOutcome
from django.core.cache import cache

logger = logging.getLogger(__name__)

# One denied-access event per user, path and reason per window: enough to see probing
# without letting a loop flood the table.
DENIED_WINDOW_SECONDS = 300


def audit(actor, action, resource_type, resource_id, *, request_id=None, **metadata):
    """Record a successful action by `actor`."""
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        outcome=AuditOutcome.SUCCEEDED,
        request_id=request_id,
        metadata=metadata,
    )


def audit_denied(actor, *, path, method, code, request_id=None):
    """Record a refused request by a signed-in user (rate-limited per user/path/code)."""
    key = f'audit-denied:{actor.pk}:{method}:{path}:{code}'
    if not cache.add(key, 1, DENIED_WINDOW_SECONDS):
        return None
    try:
        return AuditEvent.objects.create(
            actor=actor,
            action='access.denied',
            resource_type='endpoint',
            resource_id=path[:128],
            outcome=AuditOutcome.DENIED,
            request_id=request_id,
            metadata={'method': method, 'code': code},
        )
    except Exception:
        # Auditing a refusal must never turn it into a 500.
        logger.exception('Could not record a denied-access audit event')
        return None
