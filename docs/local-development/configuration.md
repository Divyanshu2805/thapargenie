# Configuration

Every setting is an environment variable. Locally they come from `Backend/backend/.env`
and `Frontend/.env.local`; in production from the host. Neither file is committed.

Two kinds of setting are **not** here, because admins change them at runtime from
**Admin → Settings**: the daily question limit, the AI budget, maintenance mode, the
banner, approval, reranking, the cache and the starter questions. Those live in the
database (`ChatSettings`); see the [admin API](../api/admin.md#settings).

## API

`APP_ENV` picks the settings profile: `local` (default), `test` or `production`.

### Core

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` | none | PostgreSQL with pgvector. Locally the `compose.yml` database |
| `DATABASE_SSL_REQUIRE` | `false` | `true` for a hosted database from a local machine |
| `DJANGO_SECRET_KEY` | random per start (local) | Also encrypts staff two-factor keys, so set a fixed one if you use two-factor locally |
| `DJANGO_DEBUG` | `true` (local) | Opens the OpenAPI pages to everyone |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `http://localhost:5173` | The web app's origin |
| `DJANGO_ADMIN_ENABLED` | `true` (local), `false` (production) | The Django admin at `/admin/` |
| `TIME_ZONE` | `Asia/Kolkata` | Decides when "today" starts for limits and statistics |

### Sign-in

| Variable | Default | |
|---|---|---|
| `FIREBASE_PROJECT_ID` | none | The project the web app signs in to |
| `GOOGLE_APPLICATION_CREDENTIALS` | none | Path to a service-account JSON, used to check for revoked sessions |
| `FIREBASE_AUTH_EMULATOR_HOST` | empty | Host and port of the Auth emulator, without a scheme. Refused in production |
| `FIREBASE_ALLOWED_SIGN_IN_PROVIDERS` | `password,google.com` | |
| `FIREBASE_RECENT_AUTH_SECONDS` | `300` | How fresh a sign-in must be for irreversible actions |
| `FIREBASE_REVOCATION_CACHE_SECONDS` | `60` | How long a confirmed student token is trusted without asking Firebase again (0 to 300). Staff are always checked |
| `FIREBASE_CLOCK_SKEW_SECONDS` | `10` | Clock drift allowed when reading token times |
| `FIREBASE_HTTP_POOL_SIZE` | `GUNICORN_THREADS` | Connections kept to Google for the revocation check |
| `OPEN_ACCESS_EMAIL_DOMAINS` | `thapar.edu` | With approval switched off, only verified addresses on these domains get in directly. Empty allows any |
| `STAFF_TWO_FACTOR_REQUIRED` | `true` | `false` switches the staff second step off |
| `STAFF_TWO_FACTOR_SESSION_HOURS` | `12` | How long a passed check lasts (1 to 720) |

### Models

| Variable | Default | |
|---|---|---|
| `LLM_PROVIDER`, `EMBED_PROVIDER` | `gemini` | `gemini`, `openai` or `offline` |
| `GEMINI_API_KEY`, `OPENAI_API_KEY` | none | For the chosen provider |
| `CHAT_MODEL` | none | Writes answers and reads scanned PDFs |
| `FAST_MODEL` | none | Analysis, reranking, titles, summaries, suggestions; also the fallback for the chat model |
| `EMBED_MODEL` | none | Embeddings |
| `EMBED_DIMENSIONS` | `768` | Must stay 768, the size of the vector columns |
| `EMBED_BATCH_SIZE` | `50` | Texts per embedding request |
| `FAST_THINKING` | `minimal` | Reasoning level for quick structured calls |
| `ANSWER_THINKING` | `low` | Reasoning level for the streamed answer |
| `LLM_TIMEOUT_SECONDS` | `60` | Per model call |
| `LLM_MAX_ATTEMPTS` | `3` | Tries per call before falling back |
| `RETRIEVE_PARALLEL` | `true` | Run the keyword search while the question is embedded |
| `OFFLINE_LLM_DELAY_MS` | `60` | Per-word delay of the offline provider |

Model names change often; `.env.example` holds the ones in use, and the provider's
documentation has the current list.

### Knowledge base

| Variable | Default | |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | none | The private bucket for uploaded files |
| `SUPABASE_BUCKET` | `documents` | |
| `STORAGE_BACKEND` | `supabase` | `memory` keeps uploads in the server process, for tests. Refused in production |
| `INGEST_URL_ALLOWLIST` | `thapar.edu,*.thapar.edu,static.npfs.co` | Domains pages may be added from |
| `INGEST_MAX_FILE_MB` | `25` | Per uploaded file (1 to 50) |
| `INGEST_MAX_PAGES` | `300` | Per PDF (1 to 2,000) |
| `EXTERNAL_HTTP_TIMEOUT_SECONDS` | `10` | For fetching pages |

### Limits and retention

| Variable | Default |
|---|---|
| `THROTTLE_USER` | `120/min` |
| `THROTTLE_ASK` | `6/min` |
| `THROTTLE_SUGGEST` | `10/min` |
| `THROTTLE_ADMIN_WRITE` | `30/min` |
| `THROTTLE_EXPORT` | `5/hour` |
| `THROTTLE_ADMIN_EXPORT` | `30/hour` |
| `THROTTLE_SITE_FEEDBACK` | `5/hour` |
| `THROTTLE_SHARED_VIEW` | `60/min` |
| `THROTTLE_CLIENT_ERROR` | `20/min` |
| `RETENTION_CONVERSATION_DAYS` | `180` |
| `RETENTION_TRACE_DAYS` | `30` |
| `RETENTION_USAGE_DAYS` | `400` |
| `RETENTION_AUDIT_DAYS` | `365` |
| `RETENTION_SITE_FEEDBACK_DAYS` | `365` |
| `RETENTION_NOTICE_DAYS` | `365` |
| `RETENTION_FAILED_DOCUMENT_DAYS` | `30` |

### Database tuning

| Variable | Default | |
|---|---|---|
| `DATABASE_CONN_MAX_AGE` | `0` (local), `60` (production) | Seconds a connection is reused |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5` | |
| `DATABASE_STATEMENT_TIMEOUT_MS` | `30000` | Set on every new connection |
| `DATABASE_LOCK_TIMEOUT_MS` | `5000` | Set on every new connection |
| `DATABASE_TRANSACTION_POOLING` | `false` | `true` with Supabase's transaction pooler (port 6543). Needed above about 2 workers of 16 threads; `check --deploy` warns otherwise |

### Logging and errors

| Variable | Default | |
|---|---|---|
| `LOG_FORMAT` | `text` | `json` writes one object per line |
| `LOG_LEVEL` | `INFO` | |
| `LOG_ACCESS` | `true` | One line per request: method, path, status, duration. Never the query string or body |
| `SENTRY_DSN` | empty | Turns on error tracking. Bodies, headers, cookies and user details are stripped |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` | |
| `APP_RELEASE` | `RENDER_GIT_COMMIT`, else `dev` | Tags logs and errors with the deploy |

### Production only

`settings/production.py` refuses to start when one of these is missing or unsafe.

| Variable | Rule |
|---|---|
| `APP_ENV` | `production` |
| `DJANGO_SECRET_KEY` | At least 50 characters |
| `DJANGO_ALLOWED_HOSTS` | Explicit host names; `*` is refused |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `https://` only |
| `DATABASE_URL`, `FIREBASE_PROJECT_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CHAT_MODEL`, `FAST_MODEL`, `EMBED_MODEL`, and the key for the chosen provider | Required |
| `TRUSTED_PROXY_COUNT` | The number of proxies that append to `X-Forwarded-For` (3 on Render). See [deployment](../deployment/README.md#the-proxy-count) |

The server process is configured in `gunicorn.conf.py`:

| Variable | Default | |
|---|---|---|
| `WEB_CONCURRENCY` | `2` | Worker processes |
| `GUNICORN_THREADS` | `8` | Threads per worker. Each streaming answer holds one |
| `GUNICORN_TIMEOUT` | `120` | Seconds before a stuck worker is killed |
| `GUNICORN_MAX_REQUESTS` | `10000` | Requests before a worker is recycled |
| `GUNICORN_LOG_LEVEL` | `info` | |
| `SECURE_SSL_REDIRECT` | `true` | |
| `SECURE_HSTS_SECONDS` | `31536000` | |

## Web app

`Frontend/.env.local`. Everything named `VITE_*` is built into the JavaScript and visible
to anyone, so no secret goes here.

| Variable | |
|---|---|
| `VITE_API_BASE_URL` | The API, for example `http://127.0.0.1:8000/api/v1/` |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID` | The Firebase web app config |
| `VITE_FIREBASE_AUTH_EMULATOR_URL` | Only with the Auth emulator. A build that sets it with an HTTPS API fails on purpose |
| `VITE_APP_RELEASE` | The git commit of the build, attached to browser error reports |

## Tests

| Variable | |
|---|---|
| `TEST_DATABASE_URL` | Database for `pytest`; defaults to `DATABASE_URL`. Django creates a separate `test_` database in it |
| `RUN_FIREBASE_EMULATOR_TESTS` | `1` runs the three tests that need the Auth emulator |
| `E2E_DATABASE_URL`, `E2E_PYTHON` | Database and Python interpreter for the end-to-end run |
