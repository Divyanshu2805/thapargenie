# Configuration

## API (`Backend/backend/.env`)

Copy `.env.example` and fill it in. `APP_ENV` picks the settings profile: `local`, `test` or
`production`.

| Variable | |
|---|---|
| `DATABASE_URL` | PostgreSQL with pgvector. Locally: the `compose.yml` database. |
| `DJANGO_SECRET_KEY` | Any long random string. |
| `FIREBASE_PROJECT_ID` | The Firebase project the web app signs in to. |
| `FIREBASE_AUTH_EMULATOR_HOST` | Only when using the Firebase Auth emulator. |
| `GEMINI_API_KEY` | For embeddings and answers. |
| `CHAT_MODEL`, `FAST_MODEL`, `EMBED_MODEL` | Model names. Check the provider docs for current ones. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | The private bucket for uploaded files. |
| `INGEST_URL_ALLOWLIST` | Domains pages may be added from. |
| `INGEST_MAX_FILE_MB`, `INGEST_MAX_PAGES` | Upload limits. |
| `THROTTLE_*` | Request rate limits: `USER` 120/min, `ASK` 6/min, `SUGGEST` 10/min, `ADMIN_WRITE` 30/min, `EXPORT` 5/hour, `CLIENT_ERROR` 20/min, `SITE_FEEDBACK` 5/hour, `ADMIN_EXPORT` 30/hour, `SHARED_VIEW` 60/min. |
| `LLM_PROVIDER`, `EMBED_PROVIDER`, `OPENAI_API_KEY` | Switch to OpenAI. |
| `FAST_THINKING`, `ANSWER_THINKING` | Reasoning level for quick calls and for answers. |
| `RETENTION_*_DAYS` | How long chats, traces, usage and logs are kept. |
| `LOG_FORMAT`, `SENTRY_DSN` | JSON logs and optional error tracking. |
| `STORAGE_BACKEND=memory`, `LLM_PROVIDER=offline` | Local end-to-end runs without real services. |

The daily question limit and the starter questions live in the database
(`ChatSettings`) and can be changed from the admin settings page.

### Production only

`settings/production.py` refuses to start if a required value is missing or unsafe.

| Variable | |
|---|---|
| `APP_ENV` | `production`. |
| `DJANGO_SECRET_KEY` | At least 50 characters. |
| `DJANGO_ALLOWED_HOSTS` | The API's host names. `*` is refused. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | The web app's origin, `https://` only. |
| `TRUSTED_PROXY_COUNT` | Proxies in front of the API (1 on Render), so rate limits use the real client address. |
| `DJANGO_ADMIN_ENABLED` | Keep `false`; the Django admin is off in production. |
| `FIREBASE_ALLOWED_SIGN_IN_PROVIDERS` | Default `password,google.com`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the Firebase service account JSON, used to check for revoked sessions. |
| `SUPABASE_BUCKET` | Default `documents`. |
| `EMBED_DIMENSIONS` | Must stay 768, the size of the vector columns. |
| `APP_RELEASE` | Tags logs and errors with the deploy; falls back to `RENDER_GIT_COMMIT`. |
| `WEB_CONCURRENCY`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | Workers, threads per worker and request timeout (2, 8, 120 s). See `gunicorn.conf.py`. |

`offline` providers and `memory` storage are refused in production.

## Web app (`Frontend/.env.local`)

| Variable | |
|---|---|
| `VITE_API_BASE_URL` | The API, e.g. `http://127.0.0.1:8000/api/v1/`. |
| `VITE_FIREBASE_*` | The Firebase web app config. |
| `VITE_FIREBASE_AUTH_EMULATOR_URL` | Only when using the Firebase Auth emulator. Never in a production build. |
| `VITE_APP_RELEASE` | The git commit of the build, attached to browser error reports. |

`VITE_*` values are built into the JavaScript and visible to anyone, so no secrets go here.
