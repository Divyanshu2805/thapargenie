# Troubleshooting

Problems that have come up while working on ThaparGenie, with the cause and the fix.

## Starting up

| Symptom | Cause and fix |
|---|---|
| `DATABASE_URL is required` | The local database is not configured. `docker compose up -d db`, and keep the `DATABASE_URL` from `.env.example` |
| `relation "django_cache" does not exist` | `python manage.py createcachetable` has not been run for this database |
| `type "halfvec" does not exist` | The database is not the pgvector image, or `migrate` has not run. The first `common` migration creates the extensions |
| `CHAT_MODEL is not set` | The three model names have no defaults. Copy them from `.env.example` |
| Every answer is "I couldn't find this" | The knowledge base is empty. Add a document, or run `import_crawler_export` |
| The API will not start with `APP_ENV=production` | By design: a required value is missing or unsafe. The message names it |

## Signing in

| Symptom | Cause and fix |
|---|---|
| Stuck on "waiting for approval" | New accounts are pending. Run `invite_identity` for the address, or approve it from **Admin → Users & invites** |
| `/admin/` shows "set up two-factor" locally | Set `STAFF_TWO_FACTOR_REQUIRED=false` in `.env`, or enrol with an authenticator app |
| Two-factor asks to be reset after a restart | `DJANGO_SECRET_KEY` is empty locally, so a new one is generated each start and the stored key cannot be read. Set a fixed value |
| 401 right after signing in | The server clock is behind Google's. `FIREBASE_CLOCK_SKEW_SECONDS` allows 10 seconds; fix the clock beyond that |
| `identity_service_unavailable` | The API cannot reach Firebase, or `GOOGLE_APPLICATION_CREDENTIALS` does not point at a readable service-account file |
| Google sign-in popup closes at once | The origin is not in Firebase's authorized domains |
| The browser blocks requests with a CORS error | The web app's origin is not in `CORS_ALLOWED_ORIGINS`. A custom request header must also be in `CORS_ALLOW_HEADERS` |

## Asking

| Symptom | Cause and fix |
|---|---|
| Asking answers 406 | The request did not accept JSON. Send `Accept: text/event-stream, application/json`: content negotiation runs before the view |
| `conversation_busy` for a few minutes after a crash | A stream was left open. It stops blocking after 4 minutes and is marked failed after 10 |
| The first word takes about 8 seconds | Expected with the current models: analysis, embedding, search and the model's own thinking come first. See [known gaps](../known-gaps/README.md#speed) |
| Gemini answers 429 during an import | The free tier's rate limit. The client retries with the delay the API asks for; lower `EMBED_BATCH_SIZE` if it keeps happening. A daily quota error stops the import, which can be run again later |

## Documents

| Symptom | Cause and fix |
|---|---|
| A document stays `queued` | The job was lost in a restart. The recovery loop picks it up within 5 minutes under gunicorn; with `runserver`, run `python manage.py process_documents` |
| "No text could be extracted" | A scanned PDF read with the fast parser. Reprocess it with the smart parser |
| "The original file is missing" | The row has no stored file, usually after switching `STORAGE_BACKEND` |
| A URL is refused | The host is not in `INGEST_URL_ALLOWLIST`, the link is not HTTPS, or it redirects somewhere that is not allowed |

## Tests

| Symptom | Cause and fix |
|---|---|
| A test that streams hangs or sees no data | A worker thread cannot see the test's transaction. Tests stream inline (`SSE_INLINE=True`) and search without the thread pool (`RETRIEVE_PARALLEL=False`); keep it that way |
| Changing a throttle rate in a test has no effect | DRF copies rates onto the throttle classes at import. Patch `Throttle.THROTTLE_RATES` with `mock.patch.dict`, not the setting |
| A user's new state is ignored between two requests | With `force_authenticate` the user object is not reloaded. Call `refresh_from_db()` |
| `assertLogs` records lack the request id | It captures with its own handler, so handler filters do not run. Apply `RequestContextFilter` in the test |
| End-to-end: "port taken" from the emulator | An Auth emulator is already running on 9099. Reuse it by setting `FIREBASE_AUTH_EMULATOR_HOST` and running `npm run test:e2e` directly |
| End-to-end: the verify-email page says "invalid link" | The tests must run against a production build. The dev server's StrictMode runs effects twice and burns the one-time code |

## Windows

- A Playwright `webServer` command runs under `cmd.exe`, so a relative path to an
  executable needs backslashes (`..\.venv\Scripts\python.exe`).
- Run `docker run -v …` from PowerShell; Git Bash rewrites container paths. The load-test
  scripts set `MSYS_NO_PATHCONV=1` for this reason.
- `gunicorn` does not run on Windows. Use `runserver` locally; the load test runs gunicorn
  in a container.
