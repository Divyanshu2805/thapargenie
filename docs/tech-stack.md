# Tech stack

What ThaparGenie is built with, and what each piece is for. Versions are the ones locked in
`Backend/requirements.txt` and `Frontend/package.json`.

## Backend

| Piece | Version | For |
|---|---|---|
| Python | 3.13 | |
| Django | 5.2 | The framework: ORM, migrations, settings, security middleware |
| Django REST Framework | 3.18 | Views, serializers, permissions, throttles |
| drf-spectacular | 0.30 | The OpenAPI schema, generated from the code |
| psycopg | 3.3 | The PostgreSQL driver |
| pgvector | 0.5 | Vector fields and HNSW indexes from Django |
| firebase-admin | 7.6 | Verifying ID tokens and checking revocation |
| google-genai | 2.25 | Gemini: embeddings, answers, PDF reading |
| openai | 3.19 | The alternative provider |
| httpx | 0.28 | Fetching web pages and calling Supabase Storage |
| pypdf, python-docx, openpyxl, trafilatura | 6.19, 1.2, 3.1, 2.2 | Reading PDF, Word, Excel and HTML |
| cryptography | 50.0 | Encrypting staff two-factor keys |
| gunicorn | 26.2 | The production server, threaded workers |
| whitenoise | 6.12 | Static files for the OpenAPI page |
| sentry-sdk | 2.70 | Optional error tracking |

Every runtime dependency has a permissive licence (MIT, BSD or Apache). PyMuPDF was turned
down for its AGPL licence.

## Data

| Piece | For |
|---|---|
| PostgreSQL 17 | Everything durable |
| pgvector | `halfvec(768)` embeddings with HNSW indexes |
| Full-text search | A generated `tsvector` column with a GIN index, English configuration |
| `pg_trgm` | Title search |
| Supabase | Hosts the database and a private storage bucket. Its auth and REST API are not used |

## Models

| Role | Model in production | Used for |
|---|---|---|
| Chat | `gemini-3.8-flash` | Writing answers, reading scanned PDFs |
| Fast | `gemini-3.5-flash-lite` | Query analysis, reranking, titles, summaries, suggestions, context sentences; fallback for the chat model |
| Embedding | `gemini-embedding-2`, 768 dimensions | Passages and questions |

Model names are configuration (`CHAT_MODEL`, `FAST_MODEL`, `EMBED_MODEL`), not code.

## Web app

| Piece | Version | For |
|---|---|---|
| React | 19.3 | |
| Vite | 8.3 | Dev server and build |
| React Router | 7.18 | Routes and code splitting |
| TanStack Query | 5.103 | Server state and caching |
| Tailwind CSS | 4.3 | Styling |
| Radix UI (through shadcn/ui) | 1.6 | Accessible primitives: dialogs, menus, tabs, tooltips |
| Firebase JS SDK | 12.19 | Sign-in and tokens |
| react-markdown with remark-gfm | 10.1 | Rendering answers, tables included, with no raw HTML |
| lucide-react | 1.48 | Icons |
| sonner | 2.0 | Toasts |
| react-day-picker | 10.0 | Date fields in the admin |
| qrcode-generator | 2.0 | The two-factor setup QR code |
| lenis | 1.3 | Smooth scrolling on the landing page |
| Plus Jakarta Sans (self-hosted) | 5.3 | The typeface |

Node 24 and npm 11.

## Tooling

| Piece | For |
|---|---|
| pytest, pytest-django, pytest-cov | Backend tests and coverage |
| ruff | Python lint: errors, imports, bugbear, security (`S`) and Django rules |
| Vitest, Testing Library, happy-dom | Frontend tests |
| Playwright | End-to-end tests |
| ESLint, knip, Prettier | Lint, unused-code detection, formatting |
| pip-audit, npm audit, gitleaks | Dependency advisories and secret scanning |
| uv | Compiling the hash-locked requirement files |
| Locust, toxiproxy | The load test |
| Docker Compose | The local database and the load-test stack |

## Hosting and services

| Service | For |
|---|---|
| Firebase Hosting | The web app |
| Render | The API |
| Supabase | Database and file storage |
| Firebase Authentication | Sign-in |
| Google AI Studio | Gemini API access and its spend cap |
| GitHub Actions | CI, the frontend deploy and scheduled jobs |
| Cloudflare | DNS for the custom domain |
| UptimeRobot, Sentry | Uptime checks and error tracking |
