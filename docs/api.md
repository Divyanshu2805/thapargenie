# API

All endpoints are under `/api/v1/`. Requests carry `Authorization: Bearer <Firebase ID token>`.
Errors look the same everywhere:

```json
{"error": {"code": "daily_quota_exceeded", "message": "…", "request_id": "…"}}
```

The full OpenAPI schema is at `/api/v1/schema/` (Swagger UI at `/api/v1/docs/`), open to
staff, or to everyone with `DJANGO_DEBUG=true`.

## Public

| Method | Path | |
|---|---|---|
| GET | `/health/live/` | The process is up. No dependencies checked; for the host's health check. |
| GET | `/health/ready/` | The database answers. For an uptime monitor. |
| POST | `client-errors/` | Browser error reports. No token read; capped and scrubbed. |

## Account

| Method | Path | |
|---|---|---|
| GET, PATCH | `me/` | Who is signed in, approval state, profile (campus, programme, year). |
| POST | `me/revoke-sessions/` | Sign out everywhere. Needs a recent sign-in. |
| GET | `me/export/` | All my chats as a JSON download. |

## Chat

| Method | Path | |
|---|---|---|
| GET | `app-config/` | Starter questions, questions left today, banner, maintenance, notices. |
| GET, POST | `conversations/` | List (newest first) or start a conversation. |
| GET, PATCH, DELETE | `conversations/<id>/` | Rename or delete one. |
| GET | `conversations/<id>/messages/` | The messages with their sources and feedback. |
| POST | `conversations/<id>/messages/` | Ask a question. Streams the answer (see below). |
| PUT, DELETE | `messages/<id>/feedback/` | Thumbs up or down, with a reason for down. |
| GET | `sources/<id>/open/` | A link to a cited source (a signed link for uploaded files). |
| DELETE | `conversations/` | Delete all my chats. Needs a recent sign-in. |
| POST | `messages/<id>/regenerate/` | A new version of an answer (streams). |
| POST | `messages/<id>/suggestions/` | Follow-up questions, generated once and kept. |
| GET, POST, DELETE | `messages/<id>/share/` | The 7-day public link to an answer. |
| GET | `shared/<token>/` | A shared answer. Public. |
| GET | `coverage/` | Topics the knowledge base covers. |
| GET, POST | `site-feedback/` | Feedback about the site. |
| GET | `notices/`, `notices/official/` | Notices from admins and new official documents. |
| GET | `notices/official/<id>/open/` | A link to an official document. |

`conversations/` takes `archived`, `pinned` and `q` (search in titles and messages).
`PATCH conversations/<id>/` also takes `is_pinned`, `is_archived` and `current_leaf_id`
(switch to another branch). Asking with `edit_of` starts a new branch from that question.

### Streaming

Asking returns `text/event-stream` with these events:

- `meta`: ids of the saved question and answer, and questions left today.
- `status`: what is happening right now (`understanding`, `searching`, `reading`, `writing`).
- `sources`: the numbered sources.
- `delta`: the next piece of the answer (many of these).
- `done`: the saved answer, or `error` with a code and whether retrying makes sense.

Send a `client_request_id` (a UUID) with every question. Retrying with the same id never
creates a second copy of the question.

## Admin

Staff only, under `admin/`. Deleting anything needs a recent sign-in.

| Method | Path | |
|---|---|---|
| GET, POST | `documents/` | List with filters, or upload files (multipart). |
| POST | `documents/url/`, `documents/text/` | Add a web page or a piece of text. |
| GET, PATCH, DELETE | `documents/<id>/` | One document. |
| POST | `documents/<id>/reprocess/`, `enable/`, `disable/` | Change its state. |
| GET | `documents/<id>/file/` | A signed link to the original. |
| POST | `documents/bulk/` | One action on up to 100 documents. |
| GET | `documents/ids/` | Every id matching the list filters. |
| POST | `documents/suggest-details/` | Suggested session and issue date. |
| GET, PATCH, DELETE | `documents/<id>/chunks/`, `chunks/<id>/` | View and edit passages. |
| GET | `stats/`, `gaps/`, `complaints/`, `feedback/`, `site-feedback/` | Insight. `complaints/` lists remarks about an earlier answer with the question it followed. |
| GET | `stats/export/`, `gaps/export/`, `feedback/export/` | The same as CSV. |
| PATCH | `feedback/<id>/`, `site-feedback/<id>/` | Review: resolve, dismiss, add a note. |
| GET, PATCH | `settings/` | Limits, maintenance mode, banner, starter questions. |
| POST | `playground/` | Run a question through the pipeline without saving it. |
| GET, POST | `users/`, `invitations/`, `audit-log/` | Access and history. |
| PATCH | `users/<id>/` | Approve, suspend or deny, with a reason. |
| DELETE | `invitations/<id>/` | Revoke an invitation. |
| GET, POST | `notices/` | List or post notices. |
| GET, PATCH, DELETE | `notices/<id>/` | One notice. |
