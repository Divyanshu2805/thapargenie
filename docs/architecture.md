# Architecture

Two parts: a Django API in `Backend/backend` and a React app in `Frontend`. They talk over
JSON, except answers, which stream as server-sent events.

## Where it runs

| Part | Host |
|---|---|
| Web app | Firebase Hosting, at [thapargenie.divyanshuagrahari.dev](https://thapargenie.divyanshuagrahari.dev) |
| API | Render web service, Singapore (`thapargenie-api.onrender.com`) |
| Database and uploaded files | Supabase, Singapore |
| Sign-in | Firebase Authentication (a production project separate from development) |
| Answers and embeddings | Google Gemini API |
| Scheduled jobs | GitHub Actions: daily purge and search-quality check, weekly encrypted backup |

## Backend apps

| App | What it holds |
|---|---|
| `userauths` | The user model, student profile and invitations. |
| `api` | Firebase token checks, `/me`, health checks and the audit log model. |
| `common` | Shared helpers: model mixins, error envelope, throttles, SSE, safe URL fetching. |
| `knowledge` | Documents and chunks, file storage and the ingestion pipeline. |
| `rag` | The model clients (Gemini, OpenAI), search, evaluation and the answer pipeline. |
| `chat` | Conversations, messages, sources, feedback, quotas and the chat API. |
| `access` | Admin endpoints for users, invitations and the audit log. |
| `notices` | Announcements posted by admins, optionally answerable. |

## Signing in

The web app signs in with Firebase. Every API request carries the Firebase ID token; the
API verifies it, maps it to a local user by Firebase UID and checks the account is approved.
Nothing else about the student is sent to the API.

## From question to answer

1. The web app creates a conversation and posts the question.
2. `chat/answering.py` checks the daily limit and saves the question plus an empty answer
   marked `streaming`, so a question is never lost.
3. `rag/pipeline.py` rewrites the question, searches, and streams the answer. See
   [answer-pipeline.md](answer-pipeline.md).
4. The finished answer is saved with its sources. If the student closes the tab, what was
   written so far is kept and marked stopped.

## Documents

Admins upload files or add pages and text. The original goes to a private Supabase bucket,
and a background thread extracts the text, splits it into chunks and embeds them.
Details are in [ingestion.md](ingestion.md).

## Web app

`Frontend/src` is split by feature: `features/chat`, `features/admin`, `features/settings`
and so on. Shared UI lives in `components`, API calls in `lib/api`, and the Firebase auth code
in `auth`, `utils` and `views/auth`.
