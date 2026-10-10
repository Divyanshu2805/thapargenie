# Security guardrails

Rules a change must not break. Each has a reason and, where there is one, the test that
catches a violation. A change that needs to weaken one is raised as a decision first, never
slipped in as a workaround. The reasoning behind the model is in the
[security model](../architecture/security-model.md).

## Identity and access

- **The user comes from the verified token only.** Never read a user id, email or role from
  a request body, query string or header.
- **Every student query is scoped to the caller.** Start from
  `Conversation.objects.owned_by(request.user)` or filter on `conversation__user`. Another
  user's resource is a 404, not a 403.
- **New endpoints are closed by default.** Do not set `permission_classes = [AllowAny]` or
  `authentication_classes = []` unless the endpoint is meant to be public, and then add it
  to the public list in `common/tests/test_observability.py` with a throttle of its own.
- **Admin views subclass `AdminAPIView`.** That is what requires staff, two-factor and, for
  deletes, a recent sign-in.
- **Staff access is granted from the command line only.** No endpoint may set `is_staff`.
- **Irreversible actions need a recent sign-in** (`HasRecentFirebaseAuthentication`).
- **Accounts are never linked by email.** A Firebase UID maps to one local user.

## Data

- **No question, answer or document text in logs or audit events.** Log ids, counts, codes
  and durations.
- **Nothing that identifies a student goes to the model.** The prompt gets the question,
  recent messages and the optional campus, programme and year.
- **Admins see students under a pseudonym**, except site feedback where the student agreed
  to be contacted.
- **Uploaded files stay private.** Hand out signed links only, always with the download
  flag, and never a public URL.
- **New tables get row level security.** `secure_database` covers every table in the public
  schema on each deploy; do not exempt one.
- **A new kind of stored data gets a retention rule** in the app's `retention.py` and a
  line in the privacy notice.

## Input and output

- **Input serializers reject unknown fields** and cap every length.
- **File types come from the bytes**, never from the name or the browser's MIME type.
- **Any URL the server fetches goes through `common.safe_http.fetch`.** Never call `httpx`
  or `requests` directly on a user-supplied URL.
- **Documents are data, not instructions.** Source text stays inside `<source>` blocks; the
  model has no tools; links and citations shown to students come from the database.
- **Model output is rendered as Markdown without raw HTML**, with only `http`, `https` and
  `mailto` links.
- **SQL is parameterised.** The two places that assemble SQL text (`rag/retrieve.py`,
  `chat/admin_services.py`) build it from fixed fragments only.
- **CSV cells are passed through `common.csv_export`**, which neutralises formulas.

## Secrets and configuration

- **No secret in the repository**, in a `VITE_*` variable, in a log line or in an error
  message. `.env` files are ignored; `.env.example` holds placeholders only.
- **Production settings fail closed.** A new required setting is validated in
  `settings/production.py` and added to the CI `check --deploy` step.
- **The offline provider, in-memory storage and the Auth emulator never run in
  production.** Settings refuse them; keep it that way.
- **Dependencies are pinned**: Python with hashes, npm with exact versions, GitHub Actions
  by commit hash.

## Changes that need the owner's decision

- Anything in the [auth code](coding-conventions.md#the-auth-code).
- Loosening a rate limit, a retention period, the content security policy or CORS.
- Sending a new kind of data to a third party.
- Adding a dependency with a non-permissive licence.
