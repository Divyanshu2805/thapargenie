"""Small, injectable boundary around the Firebase Admin SDK."""

import hashlib
import threading
import time
from datetime import datetime, timezone

import firebase_admin
from django.conf import settings
from firebase_admin import auth, exceptions
from google.auth import exceptions as google_auth_exceptions

_APP_NAME = 'thapargenie-identity'
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


class _RecentlyVerified:
    """Tokens Firebase confirmed (signature, and not disabled or revoked) a moment ago.

    The revocation check is a network call to Google, about 300 ms, on every request. Within
    a short window the answer is reused for the same token. The price is that a user you
    disable or revoke in the Firebase console keeps working for at most the window.
    Everything else is still checked on every request: token expiry, the local account being
    active, its approval state and "sign out everywhere" all come from our own database.
    Staff are never served from here (see api/authentication.py).

    Per process, keyed by a hash of the token, bounded, and only successes are stored.
    """

    MAX_ENTRIES = 5000

    def __init__(self):
        self._lock = threading.Lock()
        self._entries = {}  # token hash -> (stored at, claims)

    @staticmethod
    def _key(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def get(self, token):
        window = settings.FIREBASE_REVOCATION_CACHE_SECONDS
        if window <= 0:
            return None
        with self._lock:
            entry = self._entries.get(self._key(token))
        if entry is None or time.monotonic() - entry[0] >= window:
            return None
        return dict(entry[1])

    def put(self, token, claims):
        window = settings.FIREBASE_REVOCATION_CACHE_SECONDS
        if window <= 0:
            return
        now = time.monotonic()
        with self._lock:
            if len(self._entries) >= self.MAX_ENTRIES:
                expired = [k for k, (stored, _) in self._entries.items() if now - stored >= window]
                for key in expired:
                    del self._entries[key]
                while len(self._entries) >= self.MAX_ENTRIES:
                    del self._entries[next(iter(self._entries))]  # oldest first
            self._entries[self._key(token)] = (now, dict(claims))

    def clear(self):
        with self._lock:
            self._entries.clear()


recently_verified_tokens = _RecentlyVerified()


def recently_verified(id_token):
    """The claims of a token Firebase verified within the cache window, else None."""
    return recently_verified_tokens.get(id_token)


def verify_firebase_id_token(id_token):
    """Verify an ID token with Firebase, including the disabled/revoked-user lookup.

    Always asks Firebase. A success is remembered for `recently_verified`.
    """

    try:
        claims = auth.verify_id_token(
            id_token,
            app=get_firebase_app(),
            check_revoked=True,
            clock_skew_seconds=settings.FIREBASE_CLOCK_SKEW_SECONDS,
        )
        recently_verified_tokens.put(id_token, claims)
        return claims
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
