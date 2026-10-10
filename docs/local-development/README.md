# Local development

Getting ThaparGenie running on your machine. About 15 minutes with the accounts ready.

| Page | Covers |
|---|---|
| This page | Prerequisites and first-time setup |
| [Configuration](configuration.md) | Every environment variable for the API and the web app |
| [Commands](commands.md) | Day-to-day commands and every management command |
| [Troubleshooting](troubleshooting.md) | Problems that have come up, and their fixes |

## Prerequisites

| Tool | Version | For |
|---|---|---|
| Python | 3.13 (`.python-version`) | The API |
| Node.js | 24 (`.nvmrc`), npm 11 | The web app |
| Docker | any recent | The local PostgreSQL with pgvector |
| A Firebase project | free tier | Sign-in. Enable Email/Password and Google |
| A Gemini API key | free tier works | Embeddings and answers |
| A Supabase project | free tier | Only for uploading files; adding pages by URL and text works without it |

SQLite is not supported: search needs pgvector and Postgres full-text search.

## Setup

### 1. Database

```bash
docker compose up -d db
```

PostgreSQL 17 with pgvector on `127.0.0.1:54329`, user, password and database all
`thapargenie`.

### 2. API

```bash
python -m venv Backend/.venv
source Backend/.venv/bin/activate          # Windows: Backend\.venv\Scripts\activate
pip install -r Backend/requirements-dev.txt
cp Backend/backend/.env.example Backend/backend/.env
```

Fill in `Backend/backend/.env`: at least `FIREBASE_PROJECT_ID`, `GEMINI_API_KEY`, and
`STAFF_TWO_FACTOR_REQUIRED=false` for local work. Point `GOOGLE_APPLICATION_CREDENTIALS` at
a Firebase service-account file kept outside the repository. Then:

```bash
cd Backend/backend
python manage.py migrate
python manage.py createcachetable
python manage.py runserver
```

The API is on <http://127.0.0.1:8000>; Swagger UI is at `/api/v1/docs/`.

### 3. Web app

```bash
cd Frontend
cp .env.example .env.local      # the Firebase web app config and the API URL
npm ci
npm run dev
```

The app is on <http://localhost:5173>.

### 4. Your account

New accounts wait for approval, and staff access is granted from the command line only.

```bash
cd Backend/backend
python manage.py createsuperuser
python manage.py invite_identity you@example.com --actor-email <superuser email>
```

Register in the app with that address and verify it; the invitation approves the account.
To open the admin dashboard, copy your Firebase UID from the Firebase console and run:

```bash
python manage.py grant_firebase_staff --firebase-uid <uid> --actor-email <superuser email> --reason "local admin"
```

### 5. Some knowledge

Without documents every answer is "I couldn't find this". Either add a page or a piece of
text from **Admin → Documents**, or import a crawler export:

```bash
python manage.py import_crawler_export <folder> --dry-run   # what it would import and cost
python manage.py import_crawler_export <folder>
```

Then try it from the terminal:

```bash
python manage.py ask "What is the hostel fee?" --trace
```

## Without real services

The API can run with no Gemini key and no Supabase project:

```ini
LLM_PROVIDER=offline
EMBED_PROVIDER=offline
CHAT_MODEL=offline-chat
FAST_MODEL=offline-fast
EMBED_MODEL=offline-embed
STORAGE_BACKEND=memory
```

The offline provider is a deterministic stand-in, not a model: it quotes the first source
back. It is what the end-to-end tests and the load test use, and production settings refuse
it. Sign-in can use the Firebase Auth emulator the same way (`FIREBASE_AUTH_EMULATOR_HOST`
on the API and `VITE_FIREBASE_AUTH_EMULATOR_URL` in the web app).
