"""Audited operator services for explicit staff access changes."""

from django.db import transaction
from userauths.models import User

from api.models import AuditEvent, AuditOutcome


class StaffGrantDenied(Exception):
    pass


def set_staff_access(*, actor, target, enabled, reason, request_id=None):
    if not actor.is_active or not actor.is_superuser:
        raise StaffGrantDenied('Only an active local superuser may change staff access.')
    if not target.firebase_uid:
        raise StaffGrantDenied('Staff access requires a reviewed Firebase UID mapping.')
    reason = reason.strip()
    if not reason or len(reason) > 200:
        raise StaffGrantDenied('A non-sensitive reason of at most 200 characters is required.')

    with transaction.atomic():
        target = User.objects.select_for_update().get(pk=target.pk)
        changed = target.is_staff != enabled
        if changed:
            target.is_staff = enabled
            target.save(update_fields=['is_staff'])
        AuditEvent.objects.create(
            actor=actor,
            action='staff.granted' if enabled else 'staff.revoked',
            resource_type='user',
            resource_id=str(target.pk),
            outcome=AuditOutcome.SUCCEEDED,
            request_id=request_id,
            metadata={'changed': changed, 'reason': reason},
        )
    return target, changed
