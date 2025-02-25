"""Django REST Framework authentication for Firebase ID tokens."""

import base64
import json
import time
from datetime import datetime, timezone

from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied

from api.firebase import (
    DisabledFirebaseUser,
    ExpiredFirebaseToken,
    FirebaseIdentityUnavailable,
    InvalidFirebaseToken,
    RevokedFirebaseToken,
    verify_firebase_id_token,
)
from api.identity import (
    FirebaseIdentity,
    IdentityMappingConflict,
    resolve_local_identity,
)

MAX_ID_TOKEN_BYTES = 16 * 1024


class IdentityServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Identity verification is temporarily unavailable.'
    default_code = 'identity_service_unavailable'


def _decode_jwt_header(token):
    parts = token.split('.')
    if len(parts) != 3:
        raise InvalidFirebaseToken('The token is not a JWT.')
    encoded = parts[0]
    try:
        raw = base64.urlsafe_b64decode(encoded + ('=' * (-len(encoded) % 4)))
        header = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidFirebaseToken('The token header is invalid.') from exc
    if not isinstance(header, dict):
        raise InvalidFirebaseToken('The token header is invalid.')
    return header


def _integer_claim(claims, name):
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidFirebaseToken(f'The {name} claim is invalid.')
    return int(value)


def _validated_identity(token, claims):
    if not isinstance(claims, dict):
        raise InvalidFirebaseToken('The decoded token is invalid.')

    header = _decode_jwt_header(token)
    emulator = bool(settings.FIREBASE_AUTH_EMULATOR_HOST)
    if emulator:
        if header.get('alg') not in {'none', 'RS256'}:
            raise InvalidFirebaseToken('The emulator token algorithm is invalid.')
    elif header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
        raise InvalidFirebaseToken('The token signing header is invalid.')
    if header.get('typ') not in {None, 'JWT'}:
        raise InvalidFirebaseToken('The token type is invalid.')

    project_id = settings.FIREBASE_PROJECT_ID
    if claims.get('aud') != project_id:
        raise InvalidFirebaseToken('The token audience is invalid.')
    if claims.get('iss') != f'https://securetoken.google.com/{project_id}':
        raise InvalidFirebaseToken('The token issuer is invalid.')

    uid = claims.get('uid')
    subject = claims.get('sub')
    if not isinstance(uid, str) or not uid or len(uid) > 128 or subject != uid:
        raise InvalidFirebaseToken('The token subject is invalid.')

    now = int(time.time())
    skew = settings.FIREBASE_CLOCK_SKEW_SECONDS
    expires_at = _integer_claim(claims, 'exp')
    issued_at = _integer_claim(claims, 'iat')
    auth_time = _integer_claim(claims, 'auth_time')
    if expires_at <= now - skew or issued_at > now + skew or auth_time > now + skew:
        raise ExpiredFirebaseToken('The token timestamps are invalid.')

    firebase_claim = claims.get('firebase')
    if not isinstance(firebase_claim, dict):
        raise InvalidFirebaseToken('The Firebase token claim is missing.')
    sign_in_provider = firebase_claim.get('sign_in_provider')
    if sign_in_provider not in settings.FIREBASE_ALLOWED_SIGN_IN_PROVIDERS:
        raise InvalidFirebaseToken('The sign-in provider is not allowed.')

    email = claims.get('email')
    if not isinstance(email, str) or not email.strip() or len(email) > 254:
        raise InvalidFirebaseToken('The token email is invalid.')
    email = email.strip().casefold()
    email_verified = claims.get('email_verified', False)
    if not isinstance(email_verified, bool):
        raise InvalidFirebaseToken('The email verification claim is invalid.')

    return FirebaseIdentity(
        uid=uid,
        email=email,
        email_verified=email_verified,
        auth_time=auth_time,
        claims=claims,
    )


class FirebaseAuthentication(BaseAuthentication):
    keyword = b'bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if header[0].lower() != self.keyword or len(header) != 2:
            raise AuthenticationFailed('A valid Bearer token is required.', code='invalid_bearer')
        if len(header[1]) > MAX_ID_TOKEN_BYTES:
            raise AuthenticationFailed(
                'The identity token is invalid.', code='invalid_identity_token'
            )
        try:
            token = header[1].decode('ascii')
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed(
                'The identity token is invalid.', code='invalid_identity_token'
            ) from exc

        try:
            claims = verify_firebase_id_token(token)
            identity = _validated_identity(token, claims)
            user = resolve_local_identity(
                identity,
                request_id=getattr(request, 'request_id', None),
            )
        except ExpiredFirebaseToken as exc:
            raise AuthenticationFailed(
                'The identity token has expired.', code='expired_identity_token'
            ) from exc
        except RevokedFirebaseToken as exc:
            raise AuthenticationFailed(
                'The identity session has been revoked.', code='revoked_identity_token'
            ) from exc
        except DisabledFirebaseUser as exc:
            raise AuthenticationFailed(
                'The identity is disabled.', code='disabled_identity'
            ) from exc
        except InvalidFirebaseToken as exc:
            raise AuthenticationFailed(
                'The identity token is invalid.', code='invalid_identity_token'
            ) from exc
        except IdentityMappingConflict as exc:
            raise PermissionDenied(
                'This identity requires administrator review.', code='identity_review_required'
            ) from exc
        except FirebaseIdentityUnavailable as exc:
            raise IdentityServiceUnavailable() from exc

        if not user.is_active:
            raise AuthenticationFailed('The local account is disabled.', code='disabled_identity')
        if user.firebase_tokens_valid_after:
            auth_time = datetime.fromtimestamp(identity.auth_time, tz=timezone.utc)
            if auth_time < user.firebase_tokens_valid_after:
                raise AuthenticationFailed(
                    'The identity session has been revoked.', code='revoked_identity_token'
                )
        return user, identity

    def authenticate_header(self, request):
        return 'Bearer'
