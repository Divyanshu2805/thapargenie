"""Race-safe mapping from verified Firebase claims to local identity records."""

from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string
from userauths.models import EligibilityState, IdentityInvitation, User

from api.models import AuditEvent, AuditOutcome


class IdentityMappingConflict(Exception):
    """The verified identity requires operator review before it can be mapped."""


@dataclass(frozen=True)
class FirebaseIdentity:
    uid: str
    email: str
    email_verified: bool
    auth_time: int
    claims: dict


def _identity_defaults(claims):
    defaults = {}
    given_name = claims.get('given_name')
    family_name = claims.get('family_name')
    if isinstance(given_name, str) and given_name.strip():
        defaults['first_name'] = given_name.strip()[:150]
    if isinstance(family_name, str) and family_name.strip():
        defaults['last_name'] = family_name.strip()[:150]
    return defaults


def _changed_fields(user, email, claims):
    values = {'email': email, **_identity_defaults(claims)}
    return {name: value for name, value in values.items() if getattr(user, name) != value}


def _sync_allowlisted_fields(user, email, claims):
    updates = []
    for field_name, value in _changed_fields(user, email, claims).items():
        setattr(user, field_name, value)
        updates.append(field_name)
    if not updates:
        return
    try:
        with transaction.atomic():
            user.save(update_fields=updates)
    except IntegrityError as exc:
        raise IdentityMappingConflict('The identity email requires operator review.') from exc


def _approve_from_invitation(user, email, request_id):
    if user.eligibility_state != EligibilityState.PENDING:
        return

    now = timezone.now()
    invitation = (
        IdentityInvitation.objects.select_for_update()
        .filter(email=email, is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .first()
    )
    if invitation is None:
        return

    invitation.accepted_by = user
    invitation.accepted_at = now
    invitation.is_active = False
    invitation.save(update_fields=['accepted_by', 'accepted_at', 'is_active'])
    user.eligibility_state = EligibilityState.APPROVED
    user.eligibility_approved_at = now
    user.save(update_fields=['eligibility_state', 'eligibility_approved_at'])
    AuditEvent.objects.create(
        actor=user,
        action='eligibility.invitation_accepted',
        resource_type='identity_invitation',
        resource_id=str(invitation.pk),
        outcome=AuditOutcome.SUCCEEDED,
        request_id=request_id,
        metadata={'method': 'verified_email_invitation'},
    )


def _open_access_enabled(email):
    # The switch lives outside the auth apps, so it is
    # named by an import path. Unset means approval is always required.
    # It is given the verified email, so it can admit some addresses and not others.
    path = getattr(settings, 'IDENTITY_OPEN_ACCESS', '')
    return bool(path) and bool(import_string(path)(email))


def _approve_open_access(user, request_id):
    if (user.eligibility_state != EligibilityState.PENDING
            or not _open_access_enabled(user.email)):
        return

    user.eligibility_state = EligibilityState.APPROVED
    user.eligibility_approved_at = timezone.now()
    user.save(update_fields=['eligibility_state', 'eligibility_approved_at'])
    AuditEvent.objects.create(
        actor=user,
        action='eligibility.auto_approved',
        resource_type='user',
        resource_id=str(user.pk),
        outcome=AuditOutcome.SUCCEEDED,
        request_id=request_id,
        metadata={'method': 'open_access'},
    )


def resolve_local_identity(identity, request_id=None):
    """Return exactly one UID-bound user; never link an old account by email."""

    # Fast path: an existing user with nothing to sync and no invitation to accept needs
    # no transaction or row lock. Anything else takes the locked path below.
    user = User.objects.filter(firebase_uid=identity.uid).first()
    if (
        user is not None
        and not _changed_fields(user, identity.email, identity.claims)
        and not (identity.email_verified and user.eligibility_state == EligibilityState.PENDING)
    ):
        return user

    defaults = _identity_defaults(identity.claims)
    with transaction.atomic():
        user = User.objects.select_for_update().filter(firebase_uid=identity.uid).first()
        created = False
        if user is None:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=identity.email,
                        firebase_uid=identity.uid,
                        **defaults,
                    )
                created = True
            except IntegrityError:
                user = User.objects.select_for_update().filter(firebase_uid=identity.uid).first()
                if user is None:
                    raise IdentityMappingConflict(
                        'The identity cannot be linked automatically.'
                    ) from None

        _sync_allowlisted_fields(user, identity.email, identity.claims)
        if identity.email_verified:
            _approve_from_invitation(user, identity.email, request_id)
            _approve_open_access(user, request_id)

        if created:
            AuditEvent.objects.create(
                actor=user,
                action='identity.created',
                resource_type='user',
                resource_id=str(user.pk),
                outcome=AuditOutcome.SUCCEEDED,
                request_id=request_id,
                metadata={'identity_provider': 'firebase'},
            )
        return user
