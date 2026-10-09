"""Two-factor sign-in for staff: an authenticator app (TOTP, RFC 6238) and backup codes.

Firebase proves the password or Google sign-in. This adds a second step for the admin
API, kept in our own database: a staff member enrols an authenticator app once, then
enters a code after each sign-in. A passed check is tied to that sign-in (the token's
`auth_time`) and lasts STAFF_TWO_FACTOR_SESSION_HOURS, so a stolen password alone, used
from anywhere, never reaches the admin API.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote, urlencode

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from common.audit import audit
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from access.models import SecondFactor, SecondFactorSession

ISSUER = 'ThaparGenie'
DIGITS = 6
PERIOD = 30
# Accept the step before and after the current one, for clocks that are a little off.
WINDOW = 1
RECOVERY_CODES = 10
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 5


class TwoFactorError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fernet():
    key = hashlib.sha256(b'two-factor:' + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt(secret):
    return _fernet().encrypt(secret.encode()).decode()


def _decrypt(factor):
    try:
        return _fernet().decrypt(factor.secret.encode()).decode()
    except InvalidToken as exc:
        # DJANGO_SECRET_KEY changed since enrolment: the staff member must enrol again.
        raise TwoFactorError(
            'second_factor_reset_required',
            'Two-factor sign-in must be set up again. Ask the owner to reset it.',
        ) from exc


def _hash_recovery_code(code):
    normalised = ''.join(code.split()).replace('-', '').upper()
    return hmac.new(settings.SECRET_KEY.encode(), b'recovery:' + normalised.encode(),
                    hashlib.sha256).hexdigest()


def totp(secret, counter):
    """The code for one 30-second step (RFC 4226 over a base32 secret)."""
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def _matching_counter(secret, code, after, now=None):
    """The time step `code` belongs to, if it is current and newer than `after`."""
    code = ''.join(str(code).split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = int((now if now is not None else time.time()) // PERIOD)
    for counter in range(current - WINDOW, current + WINDOW + 1):
        if counter > after and hmac.compare_digest(totp(secret, counter), code):
            return counter
    return None


def provisioning_uri(email, secret):
    label = quote(f'{ISSUER}:{email}')
    query = urlencode({'secret': secret, 'issuer': ISSUER, 'algorithm': 'SHA1',
                       'digits': DIGITS, 'period': PERIOD})
    return f'otpauth://totp/{label}?{query}'


def _new_recovery_codes():
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = base64.b32encode(secrets.token_bytes(5)).decode()  # 8 characters, 40 bits
        codes.append(f'{raw[:4]}-{raw[4:]}')
    return codes


def session_hours():
    return settings.STAFF_TWO_FACTOR_SESSION_HOURS


def session_valid(user, auth_time):
    cutoff = timezone.now() - timedelta(hours=session_hours())
    return SecondFactorSession.objects.filter(
        user=user, verified_at__gt=cutoff, auth_time=auth_time
    ).exists()


def _start_session(user, auth_time):
    now = timezone.now()
    SecondFactorSession.objects.filter(
        user=user, verified_at__lte=now - timedelta(hours=session_hours())
    ).delete()
    SecondFactorSession.objects.update_or_create(
        user=user, auth_time=auth_time, defaults={'verified_at': now}
    )


def status(user, auth_time):
    factor = SecondFactor.objects.filter(user=user, confirmed_at__isnull=False).first()
    return {
        'required': settings.STAFF_TWO_FACTOR_REQUIRED,
        'enrolled': factor is not None,
        'verified': factor is not None and session_valid(user, auth_time),
        'recovery_codes_left': len(factor.recovery_codes) if factor else 0,
        'session_hours': session_hours(),
    }


@transaction.atomic
def begin_setup(user):
    """A fresh secret to add to an authenticator app. Replaces an unconfirmed one."""
    factor = SecondFactor.objects.select_for_update().filter(user=user).first()
    if factor is not None and factor.confirmed_at:
        raise TwoFactorError('second_factor_already_set_up',
                             'Two-factor sign-in is already set up for this account.')
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    SecondFactor.objects.update_or_create(
        user=user,
        defaults={'secret': _encrypt(secret), 'confirmed_at': None, 'last_counter': 0,
                  'recovery_codes': [], 'failed_attempts': 0, 'locked_until': None},
    )
    return {'secret': secret, 'otpauth_uri': provisioning_uri(user.email, secret)}


def _locked_factor(user, *, confirmed):
    factor = SecondFactor.objects.select_for_update().filter(user=user).first()
    if factor is None or bool(factor.confirmed_at) != confirmed:
        if confirmed:
            raise TwoFactorError('second_factor_setup_required',
                                 'Set up two-factor sign-in first.')
        raise TwoFactorError('second_factor_setup_not_started',
                             'Start the setup again to get a new key.')
    if factor.locked_until and factor.locked_until > timezone.now():
        raise TwoFactorError('second_factor_locked',
                             'Too many wrong codes. Try again in a few minutes.')
    return factor


def _record_failure(factor, user, request_id):
    """Counts a wrong code. Runs outside the caller's rolled-back work on purpose."""
    factor.failed_attempts += 1
    locked = factor.failed_attempts >= MAX_FAILED_ATTEMPTS
    if locked:
        factor.failed_attempts = 0
        factor.locked_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
    factor.save(update_fields=['failed_attempts', 'locked_until'])
    if locked:
        audit(user, 'second_factor.locked', 'user', user.pk, request_id=request_id,
              minutes=LOCK_MINUTES)


def _accept(factor, counter):
    factor.last_counter = counter
    factor.failed_attempts = 0
    factor.locked_until = None


WRONG_CODE = ('second_factor_invalid_code', 'That code is not right. Check the app and try again.')


def confirm_setup(user, code, auth_time, request_id=None):
    """Finish enrolment with a first code. Returns the backup codes, shown once."""
    with transaction.atomic():
        factor = _locked_factor(user, confirmed=False)
        counter = _matching_counter(_decrypt(factor), code, factor.last_counter)
        if counter is None:
            _record_failure(factor, user, request_id)
            failed = True
        else:
            failed = False
            codes = _new_recovery_codes()
            _accept(factor, counter)
            factor.confirmed_at = timezone.now()
            factor.recovery_codes = [_hash_recovery_code(item) for item in codes]
            factor.save()
            _start_session(user, auth_time)
            audit(user, 'second_factor.enrolled', 'user', user.pk, request_id=request_id)
    if failed:
        raise TwoFactorError(*WRONG_CODE)
    return codes


def verify(user, auth_time, *, code='', recovery_code='', request_id=None):
    """Pass the second step for this sign-in with an app code or a backup code."""
    with transaction.atomic():
        factor = _locked_factor(user, confirmed=True)
        failed = False
        if recovery_code:
            hashed = _hash_recovery_code(recovery_code)
            match = next((item for item in factor.recovery_codes
                          if hmac.compare_digest(item, hashed)), None)
            if match is None:
                _record_failure(factor, user, request_id)
                failed = True
            else:
                factor.recovery_codes = [item for item in factor.recovery_codes if item != match]
                factor.failed_attempts = 0
                factor.locked_until = None
                factor.save()
                audit(user, 'second_factor.recovery_code_used', 'user', user.pk,
                      request_id=request_id, left=len(factor.recovery_codes))
        else:
            counter = _matching_counter(_decrypt(factor), code, factor.last_counter)
            if counter is None:
                _record_failure(factor, user, request_id)
                failed = True
            else:
                _accept(factor, counter)
                factor.save()
        if not failed:
            _start_session(user, auth_time)
    if failed:
        raise TwoFactorError(*WRONG_CODE)
    return status(user, auth_time)


@transaction.atomic
def regenerate_recovery_codes(user, request_id=None):
    factor = _locked_factor(user, confirmed=True)
    codes = _new_recovery_codes()
    factor.recovery_codes = [_hash_recovery_code(item) for item in codes]
    factor.save(update_fields=['recovery_codes'])
    audit(user, 'second_factor.recovery_codes_regenerated', 'user', user.pk,
          request_id=request_id)
    return codes


@transaction.atomic
def reset(user, *, actor=None, reason=''):
    """Remove a staff member's second factor, so they enrol again at their next sign-in."""
    deleted, _ = SecondFactor.objects.filter(user=user).delete()
    SecondFactorSession.objects.filter(user=user).delete()
    if deleted:
        AuditEvent.objects.create(
            actor=actor,
            actor_kind=AuditActorKind.USER if actor else AuditActorKind.SERVICE,
            action='second_factor.reset',
            resource_type='user',
            resource_id=str(user.pk),
            outcome=AuditOutcome.SUCCEEDED,
            metadata={'reason': reason[:200]},
        )
    return bool(deleted)
