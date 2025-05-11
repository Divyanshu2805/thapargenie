# ThaparGenie

A chat assistant for students of Thapar Institute of Engineering and Technology (TIET).
Ask about fees, hostels, admissions, the academic calendar, courses or rules, and get an
answer written from official college documents, with a numbered link to every source it used.

Admins add and manage the documents it answers from on a separate admin page.

## What it does

- Sign in with a college email (Firebase Auth). New accounts wait for approval.
- Ask questions and get a streamed answer with numbered citations.
- Conversations are saved; rename or delete them from the sidebar.
- Thumbs up / down on answers, with a reason for bad ones.
- A daily question limit per student.
- Admin page to upload PDFs and Word files, add web pages or plain text, and disable,
  reprocess or delete documents.

## Stack

| Part | Built with |
|---|---|
| API | Django 5.2, Django REST Framework, server-sent events for streaming |
| Database | PostgreSQL with pgvector |
| Auth | Firebase Authentication (ID tokens verified on the server) |
| Models | Google Gemini for embeddings and answers |
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
