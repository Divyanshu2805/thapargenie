# ThaparGenie

A chat assistant for students of Thapar Institute of Engineering and Technology (TIET).
Ask about fees, hostels, admissions, the academic calendar, courses or rules, and get an
answer written from official college documents, with a numbered link to every source it used.

Admins manage the knowledge base, review feedback, see which questions went unanswered and
post notices from a separate dashboard.

## What it does

- Sign in with a college email (Firebase Auth); new accounts are approved by an admin, or
  automatically when approval is switched off.
- Streamed answers with citations, a note when a figure could not be matched to a source,
  and a line saying how current the sources are.
- Hybrid search (pgvector + Postgres full-text search), question rewriting for follow-ups,
  optional reranking and a cache for repeated questions.
- Chat history with pinning, archiving, search, branches (edit a question or regenerate an
  answer), export, printing and share links.
- Follow-up suggestions, voice input and a "What can I ask?" page.
- Admin dashboard: documents (upload, URL, text, bulk actions, chunk editing), usage stats,
  feedback review, knowledge gaps, a playground, notices, users and invitations, settings
  and an audit log.

## Stack

| Part | Built with |
|---|---|
| API | Django 5.2, Django REST Framework, server-sent events for streaming |
| Database | PostgreSQL with pgvector |
| Auth | Firebase Authentication (ID tokens verified on the server) |
| Models | Google Gemini for embeddings and answers (OpenAI also supported) |
| Files | Supabase Storage (private bucket) |
| Web app | React 19, Vite, Tailwind CSS, TanStack Query |

## Running it locally

You need Python 3.13, Node 24 and Docker (for the local database).

```bash
docker compose up -d db
```

Backend:

```bash
python -m venv Backend/.venv
Backend/.venv/Scripts/activate      # or source Backend/.venv/bin/activate
pip install -r Backend/requirements-dev.txt
cp Backend/backend/.env.example Backend/backend/.env   # then fill it in
cd Backend/backend
python manage.py migrate
python manage.py createcachetable
python manage.py runserver
```

Frontend:

```bash
cd Frontend
cp .env.example .env.local   # Firebase web config and the API URL
npm ci
npm run dev
```

The app runs on http://localhost:5173 and the API on http://127.0.0.1:8000.

To make yourself an admin, sign in once, create a local superuser with
`python manage.py createsuperuser`, then run
`python manage.py grant_firebase_staff --firebase-uid <your uid> --actor-email <superuser email> --reason "local admin"`.

New student accounts wait for approval. To let one in without the admin pages, invite the
email: `python manage.py invite_identity <email> --actor-email <superuser email>`.

## Adding knowledge

Documents are added from the admin page, or in bulk:

```bash
python manage.py import_crawler_export <folder>   # the thapar.edu crawler export
python manage.py process_documents                # process anything still queued
```

## Tests

```bash
pytest                   # from the repository root, needs the local database
cd Frontend && npm test
```

## Docs

More detail is in [docs/](docs/README.md): how the pieces fit together, the API and the
settings.

## Screens

The student app lives under `/chat/`, the admin dashboard under `/admin/`. Sign-in pages,
the privacy notice and shared answers (`/s/<token>`) are public.
