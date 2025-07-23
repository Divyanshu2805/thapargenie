"""Audited access management from the admin dashboard.

Invitations follow `invite_identity` (normalised, case-insensitive unique, audited).
Staff grants are not here: they stay CLI-only through `grant_firebase_staff`.
"""

from common.audit import audit
from django.db import IntegrityError, transaction
from django.utils import timezone
from userauths.models import EligibilityState, IdentityInvitation, User

# States an admin may set. "pending" is only the state of a new account.
SETTABLE_STATES = (EligibilityState.APPROVED, EligibilityState.SUSPENDED,
                   EligibilityState.DENIED)


class AccessError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def normalize_email(email):
    return User.objects.normalize_email(email).strip().casefold()


def create_invitation(email, *, actor, expires_at=None, request_id=None):
    try:
        with transaction.atomic():
            invitation = IdentityInvitation.objects.create(
                email=normalize_email(email), created_by=actor, expires_at=expires_at
            )
            audit(actor, 'identity.invitation_created', 'identity_invitation', invitation.pk,
                  request_id=request_id, method='admin_api')
    except IntegrityError as exc:
        raise AccessError('invitation_exists',
                          'An invitation for this email already exists.') from exc
    return invitation


@transaction.atomic
def delete_invitation(invitation, *, actor, request_id=None):
    invitation = IdentityInvitation.objects.select_for_update().get(pk=invitation.pk)
    if invitation.accepted_at:
        raise AccessError('invitation_used',
                          'This invitation was already used. Suspend the user instead.')
    audit(actor, 'identity.invitation_deleted', 'identity_invitation', invitation.pk,
          request_id=request_id)
    invitation.delete()


@transaction.atomic
def set_eligibility(target, state, *, actor, reason='', request_id=None):
    if state not in SETTABLE_STATES:
        raise AccessError('invalid_state', 'That eligibility state cannot be set.')
    target = User.objects.select_for_update().get(pk=target.pk)
    if target.pk == actor.pk:
        raise AccessError('own_account', 'You cannot change your own access.')
    if target.is_staff or target.is_superuser:
        raise AccessError('staff_account',
                          'Staff access is changed from the command line only.')
    previous = target.eligibility_state
    if previous == state:
        return target
    target.eligibility_state = state
    fields = ['eligibility_state']
    if state == EligibilityState.APPROVED:
        target.eligibility_approved_at = timezone.now()
        fields.append('eligibility_approved_at')
    target.save(update_fields=fields)
    audit(actor, 'eligibility.changed', 'user', target.pk, request_id=request_id,
          previous=previous, state=state, reason=reason)
    return target
