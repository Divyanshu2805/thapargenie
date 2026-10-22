<p align="center">
  <a href="https://thapargenie.divyanshuagrahari.dev"><img src="docs/assets/banner.jpg" alt="ThaparGenie" width="900" /></a>
</p>

<p align="center">
  <b>Every answer about Thapar, straight from the source.</b><br/>
  A campus assistant that answers from official TIET documents and links every fact to its source.
</p>

<p align="center">
  <a href="https://github.com/Divyanshu2805/thapargenie/actions/workflows/ci.yml"><img src="https://github.com/Divyanshu2805/thapargenie/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
  <img src="https://img.shields.io/badge/Python-3.13-0a0b0d?logo=python" alt="Python 3.13" />
  <img src="https://img.shields.io/badge/Django-5.2-0a0b0d?logo=django" alt="Django 5.2" />
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-0a0b0d?logo=postgresql" alt="PostgreSQL with pgvector" />
  <img src="https://img.shields.io/badge/Gemini-API-0a0b0d?logo=googlegemini" alt="Gemini" />
  <img src="https://img.shields.io/badge/React-19-0a0b0d?logo=react" alt="React 19" />
  <img src="https://img.shields.io/badge/Vite-8-0a0b0d?logo=vite" alt="Vite 8" />
  <img src="https://img.shields.io/badge/Tailwind-4-0a0b0d?logo=tailwindcss" alt="Tailwind CSS 4" />
  <img src="https://img.shields.io/badge/Firebase-Auth_and_Hosting-0a0b0d?logo=firebase" alt="Firebase Authentication and Hosting" />
  <img src="https://img.shields.io/badge/Supabase-Postgres_and_Storage-0a0b0d?logo=supabase" alt="Supabase" />
  <img src="https://img.shields.io/badge/Render-API-0a0b0d?logo=render" alt="Render" />
  <img src="https://img.shields.io/badge/Playwright-E2E-0a0b0d?logo=playwright" alt="Playwright" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0a0b0d" alt="MIT License" /></a>
</p>

---

Students at Thapar Institute of Engineering and Technology (TIET) look for fees, hostel rules, cutoffs, calendars and syllabi across dozens of pages and PDFs. **ThaparGenie** answers the question directly, from the official documents, with a numbered link to every source it used, and says so plainly when the documents don't cover it.

Every figure in an answer is checked against the sources it cites before the answer is stored. Admins run the knowledge base from a separate dashboard: they upload documents, review feedback, see which questions went unanswered and post notices.

## Try it

| | |
|---|---|
| **App** | [thapargenie.divyanshuagrahari.dev](https://thapargenie.divyanshuagrahari.dev) |
| **Demo login** | `demo@thapargenie.dev` / `demo1234` |

The demo account already has a few questions asked, so you land straight in a chat with cited answers. It's shared and resets every day, so it can't change its profile or sign others out. Register with an email to get your own account. New accounts are verified by email and approved by an admin. The API sleeps when idle, so the first request after a quiet spell takes up to a minute.

<p align="center">
  <img src="docs/assets/screenshots/answer.webp" alt="A chat: a question about the hostel fee, the answer with a numbered citation, the session the sources cover and the source document" width="900" />
</p>

## Features

**Asking**
- Questions in English or Hinglish, with follow-ups understood from the chat.
- Streamed answers with a citation on every fact. Each one opens the official page or file.
- Every figure (amounts, years, dates) is matched against the sources it cites, and the answer is flagged when one isn't found.
- A line saying which academic session the sources cover, with a warning when they are out of date.
- A clear "I couldn't find this" with where to look, instead of a guess.
- "List all" questions read the whole page, so no item is left out.
- Follow-up suggestions, voice input and starter questions.

**Conversations**
- History across devices with search, pin, archive and rename.
- Branches: regenerate an answer or edit a question and flip between versions.
- Download as Markdown, print, or share one answer as a public link for 7 days.
- Notices from admins, a "What can I ask?" page, light and dark themes, and install as an app.

**Admin dashboard**
- Documents: upload PDF, Word, Excel, CSV, HTML or text, add a web page by URL, edit details, act on 100 at once, and view or edit single passages.
- Insight: usage, answer outcomes, latency, AI spend against a daily budget, feedback review, unanswered questions, and a nightly search-quality score with regression warnings.
- A playground that shows how any question was analysed, searched and answered, with the time each step took.
- Users and invitations, notices, runtime settings, CSV exports and an audit log.
- Two-factor sign-in for staff.

## Screenshots

| | |
|---|---|
| <img src="docs/assets/screenshots/home.webp" alt="The chat home screen with starter questions and the conversation history" /> | <img src="docs/assets/screenshots/admin-overview.webp" alt="The admin overview: questions per day, answer outcomes, AI calls against the daily budget and the knowledge base" /> |
| Starter questions and history | Admin overview |
| <img src="docs/assets/screenshots/admin-documents.webp" alt="The admin documents page listing documents with category, status and passage count" /> | <img src="docs/assets/screenshots/admin-playground.webp" alt="The admin playground showing an answer, whether it was grounded and the time each step took" /> |
| Documents | Playground |

Screenshots are from a local stack with sample documents.

## Results

| | |
|---|---|
| Search quality | recall@5 of **0.94 to 1.00** and MRR of 0.91 to 1.00 across four scored runs on the production knowledge base, re-scored every night |
| Capacity | **400 students** at once on half a CPU with no failed requests, across a load test of 102,194 requests |
| Speed | A full streamed answer in **10.2 s** at the median; a repeated question is served from the cache at once |
| Accessibility | Lighthouse **100** on every page measured |
| First screen | 218 kB of gzipped JavaScript; every later page loads on demand |

Every figure and how to re-check it is in [project metrics](docs/metrics.md) and [load testing](docs/load-testing.md).

## How it works

```mermaid
flowchart LR
    B["Browser<br/>(React app)"] -- "sign in" --> FA["Firebase Auth"]
    B -- "ID token, JSON and SSE" --> API["Django API"]
    API -- "verify token" --> FA
    API --> DB[("PostgreSQL<br/>pgvector + full-text")]
    API --> S[("Supabase Storage")]
    API --> G["Gemini"]
    GA["GitHub Actions<br/>scheduled jobs"] --> DB
```

| App | Owns |
|---|---|
| `chat` | Conversations as a message tree, the streaming chat API, quotas, the answer cache, sharing, feedback |
| `rag` | Model clients, question analysis, hybrid search, source building, the answer pipeline, the grounding check, evaluation |
| `knowledge` | Documents and passages, file storage, the ingestion pipeline |
| `access` | Users, invitations, the audit log, staff two-factor |
| `api`, `userauths` | Firebase token checks, identity mapping, the user model and profile |
| `notices` | Announcements |

Everything durable lives in one PostgreSQL database, and search runs there too, so there is no separate vector store, queue or cache server. Identity comes from a verified Firebase ID token on every request, a student reaches only their own chats, and the model never receives who is asking.

Each question goes like this:

```mermaid
sequenceDiagram
    participant U as Browser
    participant C as chat
    participant R as rag
    participant L as Gemini
    participant D as PostgreSQL
    U->>C: Ask a question
    C->>D: Check limits, save the question
    C->>R: Run the pipeline
    R->>L: Classify and rewrite as a standalone question
    R->>D: Vector and full-text search, fused by rank
    R->>R: Build numbered sources within a token budget
    R->>L: Answer from these sources only
    L-->>U: Answer streamed with citations
    R->>R: Match every figure to its cited source
    C->>D: Store the answer, citations and a trace
```

A greeting, a personal-record request or an off-topic question gets a fixed reply and never reaches search. The first question of a chat can be answered from a semantic cache.

More detail in [architecture](docs/architecture/README.md), [asking a question](docs/architecture/flows/asking-a-question.md) and the [security model](docs/architecture/security-model.md).

## Stack

| | |
|---|---|
| API | Python 3.13, Django 5.2, Django REST Framework, gunicorn |
| Data | PostgreSQL 17 with pgvector (`halfvec(768)`, HNSW) and full-text search |
| Models | Google Gemini for analysis, answers and embeddings, with an OpenAI adapter behind the same interface |
| Web app | React 19, Vite 8, Tailwind CSS 4, Radix UI, TanStack Query, React Router |
| Services | Firebase Authentication and Hosting, Supabase, Render, Sentry |
| Testing | pytest, Vitest, Playwright, ruff, ESLint, Locust, GitHub Actions |

Versions and what each piece is for are in the [tech stack](docs/tech-stack.md).

## Running locally

You need Python 3.13, Node 24, Docker, a Firebase project and a Gemini API key.

```bash
git clone https://github.com/Divyanshu2805/thapargenie.git
cd thapargenie
docker compose up -d db                       # PostgreSQL with pgvector

python -m venv Backend/.venv
source Backend/.venv/bin/activate             # Windows: Backend\.venv\Scripts\activate
pip install -r Backend/requirements-dev.txt
cp Backend/backend/.env.example Backend/backend/.env
cd Backend/backend
python manage.py migrate
python manage.py createcachetable
python manage.py runserver

# in another terminal
cd Frontend
cp .env.example .env.local                    # Firebase web config and the API URL
npm ci
npm run dev
```

The app is on http://localhost:5173 and the API on http://127.0.0.1:8000. Two commands help when working on answers:

```bash
python manage.py ask "question" --trace       # one question through the pipeline, step by step
python manage.py eval_rag                     # score search quality
```

Approving your account, becoming an admin, adding a knowledge base and running with no Gemini key are covered in [local development](docs/local-development/README.md).

## Testing and CI

| Suite | |
|---|---|
| Backend | 595 tests (pytest), 92% statement coverage of the answer, chat and knowledge code, with an 80% floor |
| Frontend | 246 tests (Vitest) |
| Browser | 5 Playwright journeys against the whole stack under the Auth emulator |
| Search quality | 23 fixed questions scored every night against the production knowledge base |

Every push and pull request runs a secret scan, lint, all three suites with the coverage floor, migration and OpenAPI checks, a dependency audit and a build. Work merges into `dev`, and a release is one pull request from `dev` into `main`. Once CI passes there, the web app deploys to Firebase Hosting and the API to Render. GitHub Actions also runs the scheduled jobs: the nightly search-quality score, a daily purge of expired data, a weekly encrypted backup and a weekly re-read of web pages. See [deployment](docs/deployment/README.md).

## Repository layout

```
Backend/backend/
  backend/          settings per environment, URL root, gunicorn entry
  userauths/        users, profiles, invitations
  api/              Firebase token checks, identity mapping, /me, health, audit events
  common/           throttles, event streams, safe URL fetching, logging
  knowledge/        documents and passages, storage, the ingestion pipeline
  rag/              model clients, analysis, hybrid search, the answer pipeline, evaluation
  chat/             conversations, the streaming chat API, quotas, cache, admin statistics
  access/           user and invitation management, staff two-factor
  notices/          announcements
Frontend/
  src/features/     one folder per feature: chat, admin, landing, notices, settings, ...
  src/lib/          request wrapper, stream reader, API calls
  e2e/              Playwright journeys
loadtest/           the load-test stack and its scripts
docs/               documentation
.github/workflows/  CI, the frontend deploy, scheduled jobs
```

## Docs

| | |
|---|---|
| [Features](docs/features.md) | Everything the app does, by area |
| [Architecture](docs/architecture/README.md) | The parts, request flows, security model, decision records |
| [API](docs/api/README.md) | Every endpoint, the event stream, errors and rate limits |
| [Data model](docs/schema/README.md) | Tables, indexes, conventions, retention |
| [Local development](docs/local-development/README.md) | Setup, configuration, commands, troubleshooting |
| [Deployment](docs/deployment/README.md) · [Operations](docs/deployment/operations.md) | Production, releases, scheduled jobs, backups |
| [Metrics](docs/metrics.md) · [Load testing](docs/load-testing.md) | Every measurement and how it was taken |

## License

[MIT](LICENSE) · [Privacy Policy](https://thapargenie.divyanshuagrahari.dev/privacy)
