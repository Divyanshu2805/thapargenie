# API

All endpoints are under `/api/v1/`. Requests carry `Authorization: Bearer <Firebase ID token>`.
Errors look the same everywhere:

```json
{"error": {"code": "daily_quota_exceeded", "message": "…", "request_id": "…"}}
```

The full OpenAPI schema is at `/api/v1/schema/` (Swagger UI at `/api/v1/docs/`), open to
staff, or to everyone with `DJANGO_DEBUG=true`.

## Account

| Method | Path | |
|---|---|---|
| GET, PATCH | `me/` | Who is signed in, approval state, profile (campus, programme, year). |
| POST | `me/revoke-sessions/` | Sign out everywhere. Needs a recent sign-in. |

## Chat

| Method | Path | |
|---|---|---|
| GET | `app-config/` | Starter questions and questions left today. |
| GET, POST | `conversations/` | List (newest first) or start a conversation. |
| GET, PATCH, DELETE | `conversations/<id>/` | Rename or delete one. |
| GET | `conversations/<id>/messages/` | The messages with their sources and feedback. |
| POST | `conversations/<id>/messages/` | Ask a question. Streams the answer (see below). |
| PUT, DELETE | `messages/<id>/feedback/` | Thumbs up or down, with a reason for down. |
| GET | `sources/<id>/open/` | A link to a cited source (a signed link for uploaded files). |

### Streaming

Asking returns `text/event-stream` with these events:

- `meta`: ids of the saved question and answer, and questions left today.
- `status`: what is happening right now (`searching`, `writing`).
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
