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
| `THROTTLE_USER`, `THROTTLE_ASK` | Request rate limits. |

The daily question limit and the starter questions live in the database
(`ChatSettings`, a single row) and can be changed there for now.

## Web app (`Frontend/.env.local`)

| Variable | |
|---|---|
| `VITE_API_BASE_URL` | The API, e.g. `http://127.0.0.1:8000/api/v1/`. |
| `VITE_FIREBASE_*` | The Firebase web app config. |
| `VITE_FIREBASE_AUTH_EMULATOR_URL` | Only when using the Firebase Auth emulator. |
