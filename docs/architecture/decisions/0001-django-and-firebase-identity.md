# 0001. Django REST Framework with Firebase identity

## Context

The app needs sign-in with college email addresses, email verification, password
reset and Google sign-in, plus an API with strong defaults for permissions, validation and
database access. Building and securing password handling is a project of its own.

## Decision

Firebase Authentication owns identity. The API is Django 5.2 with Django REST
Framework: it verifies the Firebase ID token on every request and maps it to one local user
by Firebase UID. Approval, staff access and everything else about authorization live in
the API's own database.

## Consequences

- No password, reset token or verification mail is handled by this codebase.
- Every request needs a token check; revocation costs a round trip to Google, which is why [ADR 0013](0013-revocation-check-cached-for-students.md) exists.
- Firebase is confined to `api/firebase.py` on the server and `auth/`, `utils/` and `views/auth` in the web app.
- Accounts are bound by UID and never linked by email, so a recycled address cannot inherit an old account.

## Alternatives considered

- **FastAPI**: lighter, but the ORM, migrations, permission classes and security middleware would be assembled by hand.
- **Django sessions and passwords**: full control, and full responsibility for credential storage and account recovery.
- **Supabase Auth**: one vendor fewer, but see [ADR 0009](0009-no-supabase-auth-or-rest-api.md).
