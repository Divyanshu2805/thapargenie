# API reference

The API the web app uses. Everything is under `/api/v1/`, plus two health checks at the
root. There are 67 routes.

| Page | Covers |
|---|---|
| [Chat](chat.md) | Account, conversations, asking and the event stream, feedback, sharing, notices |
| [Admin](admin.md) | Documents, insight, settings, users, audit log, two-factor |
| [Errors and rate limits](errors-and-rate-limits.md) | The error envelope, every error code, rate limits |

## Conventions

- **Authentication.** Every request carries `Authorization: Bearer <Firebase ID token>`.
  The exceptions are the health checks, browser error reports and shared answers.
- **JSON** in and out. Unknown fields in a request body are rejected. Uploads are
  `multipart/form-data`; answers are `text/event-stream`.
- **Ids** are UUIDs, except users, which are integers.
- **Lists** use cursor pagination: `{"next": "<url or null>", "previous": …, "results": […]}`.
  `page_size` is accepted up to a maximum per list (100 for chats, 200 for documents).
- **Trailing slashes** are part of every path.
- **`X-Request-ID`**: send a UUID and it is used; otherwise one is generated. It comes back
  as a response header, in every error body and on every log line for the request.
- **Times** are ISO 8601 in UTC. "Today", for limits and statistics, is the day in
  `Asia/Kolkata`.

## Health

| Method | Path | |
|---|---|---|
| GET, HEAD | `/health/live/` | The process is up; no dependency is checked. For the host's health check |
| GET, HEAD | `/health/ready/` | The database answers, or 503. For an uptime monitor |

## OpenAPI

The schema is generated from the code: `/api/v1/schema/`, with Swagger UI at
`/api/v1/docs/`. Both are open to staff, or to everyone when the API runs locally with
`DJANGO_DEBUG=true`. CI fails if the schema does not validate.

## Browser error reports

`POST /api/v1/client-errors/` takes `message`, and optionally `stack`, `path`, `kind`
(`render`, `error`, `rejection`, `chunk`) and `release`. No token is read. Fields are
length-capped, emails and long digit runs are masked, and the answer is always 204.
