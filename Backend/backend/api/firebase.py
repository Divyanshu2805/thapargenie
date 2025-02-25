"""Small, injectable boundary around the Firebase Admin SDK."""

import threading
from datetime import datetime, timezone

import firebase_admin
from django.conf import settings
from firebase_admin import auth, exceptions
from google.auth import exceptions as google_auth_exceptions

_APP_NAME = 'thapargpt-identity'
_APP_LOCK = threading.Lock()


class FirebaseIdentityError(Exception):
    """Base class for intentionally non-sensitive identity failures."""


class InvalidFirebaseToken(FirebaseIdentityError):
    pass


class ExpiredFirebaseToken(InvalidFirebaseToken):
    pass


class RevokedFirebaseToken(InvalidFirebaseToken):
    pass


class DisabledFirebaseUser(InvalidFirebaseToken):
    pass


class FirebaseIdentityUnavailable(FirebaseIdentityError):
    pass


def get_firebase_app():
    """Return one named Admin SDK app without initializing Firebase at import time."""

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        raise FirebaseIdentityUnavailable('Firebase project ID is not configured.')

    try:
        return firebase_admin.get_app(_APP_NAME)
    except ValueError:
        pass

    with _APP_LOCK:
        try:
            return firebase_admin.get_app(_APP_NAME)
        except ValueError:
            try:
                return firebase_admin.initialize_app(
                    options={'projectId': project_id},
                    name=_APP_NAME,
                )
            except (
                exceptions.FirebaseError,
                google_auth_exceptions.GoogleAuthError,
                ValueError,
            ) as exc:
                raise FirebaseIdentityUnavailable(
                    'Firebase Admin could not be initialized.'
                ) from exc


def verify_firebase_id_token(id_token):
    """Verify an ID token, including the Firebase disabled/revoked-user lookup."""

    try:
        return auth.verify_id_token(
            id_token,
            app=get_firebase_app(),
            check_revoked=True,
            clock_skew_seconds=settings.FIREBASE_CLOCK_SKEW_SECONDS,
        )
    except auth.ExpiredIdTokenError as exc:
        raise ExpiredFirebaseToken('The Firebase ID token has expired.') from exc
    except auth.RevokedIdTokenError as exc:
        raise RevokedFirebaseToken('The Firebase session has been revoked.') from exc
    except auth.UserDisabledError as exc:
        raise DisabledFirebaseUser('The Firebase user is disabled.') from exc
    except auth.UserNotFoundError as exc:
        raise InvalidFirebaseToken('The Firebase user no longer exists.') from exc
    except (auth.InvalidIdTokenError, ValueError) as exc:
        raise InvalidFirebaseToken('The Firebase ID token is invalid.') from exc
    except (exceptions.FirebaseError, google_auth_exceptions.GoogleAuthError) as exc:
        raise FirebaseIdentityUnavailable('Firebase token verification is unavailable.') from exc


def revoke_firebase_sessions(uid):
    """Revoke refresh tokens and return Firebase's validity watermark as UTC."""

    try:
        app = get_firebase_app()
        auth.revoke_refresh_tokens(uid, app=app)
        user_record = auth.get_user(uid, app=app)
    except (exceptions.FirebaseError, google_auth_exceptions.GoogleAuthError, ValueError) as exc:
        raise FirebaseIdentityUnavailable('Firebase session revocation is unavailable.') from exc

    timestamp_ms = user_record.tokens_valid_after_timestamp
    if timestamp_ms is None:
        raise FirebaseIdentityUnavailable('Firebase did not return a revocation watermark.')
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
