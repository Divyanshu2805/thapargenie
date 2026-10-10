# Project Metrics

Measured figures for ThaparGenie, each with how to re-check it. Nothing here is an estimate
unless it says "about". Last measured on 2026-10-11, except where a date is given.

## Quality

| Metric | Value | How to check |
|---|---|---|
| Backend tests | 572 in 56 files, all passing (3 need the Auth emulator and run in CI) | `pytest` |
| Frontend unit tests | 243 in 47 files, all passing | `cd Frontend && npm test` |
| End-to-end journeys | 5, in a real browser against the whole stack | `npm run test:e2e` under the Auth emulator |
| Statement coverage | 92% of 5,504 statements in `rag`, `chat`, `knowledge` and `notices` | `pytest --cov` |
| Coverage floor in CI | 80% | `.github/workflows/ci.yml` |
| Lint findings | 0 (`ruff`, ESLint with zero warnings allowed, `knip`) | `ruff check Backend/backend`, `npm run lint`, `npx knip` |
| CI jobs per pull request | 4: `secrets`, `backend`, `frontend`, `e2e`; all required to merge into `main` | `.github/workflows/ci.yml` |
| Dependency advisories | CI fails on any known Python advisory and on any high-severity npm advisory | `pip-audit`, `npm audit --audit-level=high` |
| Routes that answer an anonymous caller | Only the public list; a test walks every route | `common/tests/test_observability.py` |

## Answer quality

Scored on the production knowledge base against 23 fixed questions, 15 of them marked
important. Targets: recall@5 at least 0.90, MRR at least 0.70.

| Run | recall@5 | recall@10 | MRR | In sources | Full lists | Intents | Note |
|---|---|---|---|---|---|---|---|
| 2026-10-07, manual | 0.94 | 0.94 | 0.91 | | 1.00 | 1.00 | One important miss: its source document had not been added yet |
| 2026-10-08, nightly | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | |
| 2026-10-09, nightly | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | |
| 2026-10-10, nightly | 0.94 | 0.94 | 0.94 | 0.94 | 1.00 | 1.00 | One important miss, ranked 18th; see [known gaps](known-gaps/README.md#open) |

Each run makes 40 model calls. With written answers checked as well
(`eval_rag --answers`, 2026-10-06, 102 model calls): recall@5 1.00, MRR 0.97, answers 0.96.

How to check: `python manage.py eval_rag`, or **Admin → Overview → Answer quality**.

## Speed

| Metric | Value | Source |
|---|---|---|
| First word of an answer, production | about 8 s (four timed questions: 8, 14, 8, 8 s) | Stopwatch, 2026-10-09. The target of 3 s is not met |
| Full answer, production | 10.2 s median, 16.2 s at the 95th percentile | Admin Overview, 2026-10-09 |
| Cached answer | Immediate: no analysis, search or generation | `chat/cache.py` |
| Plain API request, half a CPU, 50 students | 21 ms median, 87 ms at the 95th percentile | [Load testing](load-testing.md#without-the-model) |
| Rate-limit bookkeeping | 6 SQL statements per request removed by counting in memory | [ADR 0011](architecture/decisions/0011-rate-limit-counters-in-process-memory.md) |

## Capacity

From 36 load-test runs on 2026-10-09: 102,194 requests and 11,164 streamed answers. Details
in [load testing](load-testing.md).

| Instance | Workers × threads | Result |
|---|---|---|
| Free, 0.1 CPU (production today) | 2 × 8 | 8 answers streaming at once at full speed; 37 answers a minute |
| Starter, 0.5 CPU | 2 × 8 | 16 at once; 74 answers a minute |
| Starter, 0.5 CPU | 2 × 32 | 400 students using the app at once, 229 answers a minute, first word 9.1 s, no failed requests |
| Standard, 1 CPU | 4 × 32 | About 400 answers a minute |

## Web app

Lighthouse 12, mobile emulation with simulated throttling, against the live site.

| Page | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| Landing | 72 | 100 | 100 | 100 |
| Privacy | 79 | 100 | 100 | 100 |
| Sign in | 81 | 100 | 100 | 63 |

- Sign-in is deliberately kept out of search indexes, which is the whole of its SEO
  deduction.
- Performance is held back by the largest contentful paint (6.2 s on the landing page
  under mobile throttling). Blocking time is 30 ms and layout shift is 0.
- Signed-in pages measured by hand on 2026-10-09: accessibility 100.

| Metric | Value | How to check |
|---|---|---|
| JavaScript for the first screen | 218 kB gzipped (budget 250 kB) | `npm run build`, then the entry and its preloads in `dist/index.html` |
| Stylesheet for the first screen | 25 kB gzipped | same |
| JavaScript chunks | 83; every page after the first loads on demand, and the admin area is never sent to students | `Frontend/src/App.jsx` |

## Security

| Metric | Value | Source |
|---|---|---|
| Token checks per request | Signature, audience, issuer, expiry, sign-in provider, revocation | `api/authentication.py` |
| Revocation check | Every request for staff; at most once a minute for students | `FIREBASE_REVOCATION_CACHE_SECONDS` |
| Staff second step | 6-digit code, valid for 12 hours per sign-in; 10 backup codes; 5 wrong codes lock it for 5 minutes | `access/two_factor.py` |
| Recent sign-in window | 5 minutes, for irreversible actions | `FIREBASE_RECENT_AUTH_SECONDS` |
| Signed file links | 10 minutes, download only | `knowledge/storage.py` |
| Share links | 32-character random token, 7 days, revocable | `chat/sharing.py` |
| Public objects in file storage | 0 | Private bucket |
| Tables readable through Supabase's REST API | 0 | `manage.py secure_database --check` |
| Third-party script origins allowed | 1 (`apis.google.com`, for Google sign-in) | `Frontend/csp.config.js` |
| Redirects followed when fetching a page | At most 5, each re-validated | `common/safe_http.py` |
| Audit events for a refused admin request | 1 per user, path and reason per 5 minutes | `common/audit.py` |
| Backups | Weekly, encrypted with `age`, kept 35 days | `.github/workflows/maintenance.yml` |

### Rate limits

| Scope | Limit |
|---|---|
| Any request | 120 / minute |
| Asking and regenerating | 6 / minute |
| Follow-up suggestions | 10 / minute |
| Exporting my chats | 5 / hour |
| Site feedback | 5 / hour |
| Opening a shared answer | 60 / minute per address |
| Browser error reports | 20 / minute |
| Admin changes | 30 / minute |
| Admin CSV downloads | 30 / hour |

## Product limits

| Limit | Value |
|---|---|
| Questions per student per day | 40 (admin setting) |
| Model calls per day, everyone together | 5,000 (admin setting) |
| Question length | 2,000 characters |
| Messages per conversation | 200 |
| Answers streaming at once | 1 per student |
| Upload | 25 MB and 300 pages per file, 10 files at once |
| Typed text entry | 100,000 characters |
| Bulk document action | 100 documents; "select all matching" up to 2,000 |
| CSV export | 5,000 rows |
| Follow-up suggestions | 3 per answer |
| Starter questions | 8 |
| Chats with no activity | Deleted after 180 days |

## The answer pipeline

| Setting | Value | Where |
|---|---|---|
| Phrasings searched per question | Up to 3 | `rag/analysis.py` |
| Candidates per list | 40 | `rag/retrieve.py` |
| Fusion constant | 60 | `rag/retrieve.py` |
| Boost per matching hint | At most 10% of the best score | `rag/retrieve.py` |
| Near-duplicate threshold | 85% word overlap | `rag/retrieve.py` |
| Passages sent to the model | 8 | `rag/rerank.py` |
| Source budget | 6,000 tokens; 12,000 for "list all" questions | `rag/context.py` |
| Recent messages sent verbatim | 4 | `rag/pipeline.py` |
| Cache hit threshold | Cosine similarity 0.97 | `chat/cache.py` |
| Cache lifetime | 7 days, or until the knowledge base changes | `chat/cache.py` |
| Passage size | About 450 tokens, 60 overlap; tables up to 1,200 | `knowledge/ingest/chunk.py` |
| Embedding | 768 dimensions, half precision | `knowledge/models.py` |
| Model retries | 3, then fallback to the fast model | `rag/llm/client.py` |

## Knowledge base

| Metric | Value | Source |
|---|---|---|
| Crawled pages imported | 1,341 documents, 12,666 passages | The load-test copy of the crawler import |
| Pages given context sentences in production | 652 on 2026-10-06, and the 21 longest on 2026-10-09 | `contextualize_documents` |
| Categories | 13 | `knowledge/models.py` |
| Source types | 8: PDF, Word, Excel, CSV, HTML file, web page, text, crawler import | `knowledge/models.py` |

## Scale of the codebase

| Metric | Value |
|---|---|
| Backend application code (Python, without tests and migrations) | about 14,700 lines |
| Backend test code | about 7,400 lines |
| Frontend application code (JavaScript and JSX) | about 17,500 lines, plus 7,800 of CSS |
| Frontend test code | about 4,100 lines |
| Django apps | 8 |
| Models / migrations | 20 / 15 |
| API routes | 67 |
| Management commands | 14 |
| React components | 93 files |
| Scheduled jobs | 4, plus a keep-alive ping |
| Architecture decision records | 13 |

## Re-measuring

```bash
pytest --cov --cov-report=term                 # backend tests and coverage
cd Frontend && npm test && npm run build       # frontend tests and bundle sizes
python Backend/backend/manage.py eval_rag      # search quality (about 40 model calls)
npx lighthouse https://thapargenie.divyanshuagrahari.dev --only-categories=performance,accessibility,best-practices,seo
cd loadtest && ./matrix.sh && python report.py # capacity
```
