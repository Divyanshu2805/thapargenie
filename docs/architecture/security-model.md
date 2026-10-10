# Security model

The boundaries ThaparGenie keeps, and the code that enforces each. The rules a change must
not break are restated as a checklist in [security guardrails](../practices/security-guardrails.md).

## Layers on every request

| Layer | Enforced by | Rule |
|---|---|---|
| Authentication | `api.authentication.FirebaseAuthentication` | A valid Firebase ID token, mapped to one local user by UID. See [sign-in and access](flows/authentication.md) |
| Default permission | `IsAuthenticated` + `HasVerifiedEligibleIdentity` (DRF defaults in settings) | Verified email and an approved account, on every view that does not say otherwise |
| Admin | `common.admin_api.AdminAPIView` | Staff, and a passed two-factor step |
| Recent sign-in | `HasRecentFirebaseAuthentication` | Signed in within 5 minutes, for irreversible actions |
| Ownership | `Conversation.objects.owned_by(user)` | A student reaches only their own chats; any other id is a 404, never a 403 |
| Rate limits | `common/throttles.py` | Per user, or per address when nobody is signed in |
| Business limits | `chat/answering.py` | Maintenance mode, the daily question limit, the global AI budget, one stream per student, 200 messages per chat |

A test walks the URL configuration and fails if any `/api/v1/` route answers an anonymous
caller with anything but 401 or 403, apart from a short public list
(`common/tests/test_observability.py`). A new endpoint cannot ship open by accident.

## Who may call what

| Endpoints | Caller | Extra |
|---|---|---|
| `/health/live/`, `/health/ready/` | Anyone | No data |
| `POST client-errors/` | Anyone | No token read; fields capped and scrubbed, never echoed |
| `GET shared/<token>/` | Anyone holding the link | 32-character random token; unknown, expired and revoked look the same |
| `GET me/` | Signed in, any state | So pending users can see their status |
| `PATCH me/`, all chat, notices, feedback endpoints | Verified and approved | Own data only |
| `DELETE conversations/`, `POST me/revoke-sessions/` | Verified and approved | Recent sign-in |
| `admin/**` | Staff with the second step passed | Changes are audited; every `DELETE` needs a recent sign-in |
| `admin/two-factor/**` | Staff | The only admin endpoints that answer before the second step |
| `/api/v1/schema/`, `/api/v1/docs/` | Staff | Open to everyone only with local `DJANGO_DEBUG` |
| `/admin/` (Django admin) | Nobody in production | Switched off (`DJANGO_ADMIN_ENABLED=false`) |

## Data protection

- **The model never learns who is asking.** It receives the question, recent messages and
  the optional campus, programme and year; never a name, email or id.
- **Question and answer text is never logged**, and never stored in the audit log.
- **Admins do not browse chats.** They see a rated answer or an unanswered question under a
  pseudonym. A student's email appears beside site feedback only if they agreed to be
  contacted.
- **Uploaded files** sit in a private bucket under random keys and are opened through
  signed links that last 10 minutes and always download, so an uploaded HTML file cannot
  render on the storage domain.
- **The database is closed to Supabase's REST API**: `secure_database` turns on row level
  security for every table and revokes the `anon` and `authenticated` roles, on every deploy.
- **Retention is automatic**; see the [data model](../schema/README.md#retention).
- **Students can export and delete their data** from Settings.

## Untrusted input

| Input | Handling |
|---|---|
| Uploaded files | Type detected from content; size and page limits; encrypted PDFs refused; parsed by pure-Python libraries with no macros or network |
| URLs to ingest | `common/safe_http.py`: HTTPS only, host allowlist, public addresses only, connection pinned to a checked address, redirects re-validated, body capped |
| Document text reaching the model | Wrapped in `<source>` blocks the prompt declares to be reference material, not instructions. The model has no tools, and links and citations come from the database, never from model output |
| Model output reaching the browser | Rendered as Markdown with no raw HTML, only `http`, `https` and `mailto` links, and no remote images |
| Request bodies | Unknown fields rejected; lengths capped in serializers and again by database constraints |
| CSV exports | Cells that start like a formula are neutralised |
| Browser error reports | Emails and long digit runs masked before logging |

## Browser

Firebase Hosting sends HSTS, `nosniff`, `X-Frame-Options: DENY`, a referrer policy and a
permissions policy that allows only the microphone (for voice input). The build adds a
Content-Security-Policy generated from the API and Firebase domains
(`Frontend/csp.config.js`): scripts from the app's own origin and `apis.google.com` (the
Google sign-in popup) only, no objects and no workers. The API serves data, never pages, so
its responses carry `default-src 'none'` (`common/headers.py`).

## Secrets and configuration

- Production settings refuse to start when a required value is missing or unsafe: a short
  secret key, a wildcard host, a non-HTTPS origin, the auth emulator, the offline model
  provider or in-memory storage (`settings/production.py`).
- Secrets live in Render's environment, the GitHub `production` environment and nowhere in
  the repository. `VITE_*` values are public by design.
- Logs pass through a filter that masks bearer tokens, passwords, secrets and API keys.
- CI scans every push for secrets (gitleaks) and audits dependencies (`pip-audit`,
  `npm audit`); Python dependencies are installed with hashes.

## Audit trail

`AuditEvent` rows are metadata only and kept for a year. They record identity events,
access changes, every admin change to documents, passages, notices and settings, feedback
review, exports, shares, two-factor events, scheduled jobs, and refused attempts on the
admin API (one event per user, path and reason per 5 minutes). Staff read them under
**Audit log**.

## Accepted risks

| Risk | Why it is accepted |
|---|---|
| Rate limits are counted per worker process | With 2 workers a limit can be used up to twice over. The daily question limit and the one-stream rule are exact, because they live in the database. See [ADR 0011](decisions/0011-rate-limit-counters-in-process-memory.md) |
| A student disabled in the Firebase console keeps access for up to 60 seconds | It saves a Firebase round trip on every student request; suspension inside the app applies at once. See [ADR 0013](decisions/0013-revocation-check-cached-for-students.md) |
| `style-src 'unsafe-inline'` in the content security policy | The toast library injects a style element; no user content reaches styles, and scripts stay strict |
| Rotating `DJANGO_SECRET_KEY` invalidates staff authenticator keys | Staff enrol again after a rotation |
| The restore steps have never been exercised | Documented in [operations](../deployment/operations.md#restore), not yet drilled |

To report a vulnerability, see [`SECURITY.md`](../../SECURITY.md).
