# Testing

Four layers: backend tests against a real PostgreSQL, frontend unit tests, browser tests of
the whole stack, and a scored check of search quality. No test calls a paid service.

| Suite | Size | Runs with |
|---|---|---|
| Backend (`pytest`) | 572 tests in 56 files | PostgreSQL with pgvector; a fake model provider |
| Frontend (`vitest`) | 243 tests in 47 files | happy-dom and Testing Library |
| End-to-end (Playwright) | 5 journeys in 3 files | The real API with the offline provider, a production build of the app, the Firebase Auth emulator |
| Search quality (`eval_rag`) | 23 questions | The real models, against production, nightly |

## Backend

```bash
docker compose up -d db
pytest                              # from the repository root
pytest --cov --cov-fail-under=80    # as CI runs it
```

- **A real database, always.** Search depends on pgvector and full-text search, so tests run
  on the same PostgreSQL image as production, never SQLite.
- **The model is faked.** `rag.llm.use_provider(FakeProvider())` returns deterministic
  embeddings and scripted answers, and can be told to fail the next call. No test needs an
  API key.
- **Storage is in memory** (`knowledge.storage.use_storage`).
- **Throttles are off** except in the tests that are about them. Two-factor is off except
  in its own tests, which check the codes against the RFC 6238 vectors.
- **Three tests need the Firebase Auth emulator** and are skipped without it. CI runs them
  under `firebase emulators:exec`.

Coverage is measured for `rag`, `chat`, `knowledge` and `notices`: **92%** of 5,504
statements, with CI failing below 80%. The vendor adapters (`rag/llm/gemini.py`,
`openai_provider.py`) are the main untested code, because exercising them means calling the
vendor.

What the suite is strict about:

| Area | Examples |
|---|---|
| Ownership | Another student's conversation, message, source, feedback or share link answers 404; export and delete-all touch only the caller's data |
| Authorization | A walk over every `/api/v1/` route fails if one answers an anonymous caller with anything but 401 or 403 |
| Uploads | Type from content, not name; encrypted PDFs refused; stored under random keys; signed links force a download |
| URL fetching | Private addresses, non-HTTPS links, off-allowlist hosts and unsafe redirects refused |
| Idempotency | The same `client_request_id` never creates a second question |
| Production settings | Refuse the offline provider, in-memory storage, the emulator, weak secrets and wildcard hosts |
| Retention | Each rule deletes what is due and nothing else |

## Frontend

```bash
cd Frontend
npm test            # once
npm run test:watch
```

Tests sit beside the files they cover. They concentrate on logic that is easy to get
wrong: the stream reader and its reconnect and stop paths, the message tree, the freshness
line, chat export, the request wrapper's token refresh, route guards, the two-factor gate,
and Markdown rendering that must never emit raw HTML or unsafe links. `Frontend/csp.config.test.js`
pins the content security policy.

## End-to-end

```bash
cd Frontend
npx firebase-tools emulators:exec --config ../firebase.json --only auth --project demo-thapargenie "npm run test:e2e"
```

Playwright starts the API on port 8020 with the offline provider and in-memory storage,
builds the app and serves it on 5174, and seeds accounts in the Auth emulator
(`manage.py seed_e2e`). The journeys:

- sign up, verify the email, stay signed in, read the profile, and sign out across tabs;
- ask a question, get a cited and dated answer, rate it and follow up;
- stop an answer while it streams;
- a student is kept out of the admin area;
- an admin uploads a PDF that becomes ready, marks it not current in bulk and sees the
  audit trail.

It runs against a production build on purpose; see [known pitfalls](gotchas.md#testing).

## Search quality

`rag/eval/golden.json` holds 23 questions: 17 the knowledge base should answer, most with
the page that must be found; 2 it should say it cannot find; and 4 it should not search
for at all (a greeting, a complaint about an earlier answer, a personal-record request
and an off-topic one). 15 are marked important.

```bash
python manage.py eval_rag                 # recall@5, recall@10, MRR
python manage.py eval_rag --answers       # also write and check the answers
python manage.py eval_rag --case hostels-list-all-boys --answers
```

| Measure | Meaning | Target |
|---|---|---|
| recall@5, recall@10 | Share of answerable questions whose page is in the top 5 or 10 candidates | recall@5 at least 0.90 |
| MRR | Mean of 1 / rank of the first correct candidate | at least 0.70 |
| In sources | The correct passage reached the answer prompt | |
| Full lists | For "list all" questions, every expected item reached the prompt | |
| Intents | Greetings, complaints and off-topic questions were classified correctly | |
| Answers (with `--answers`) | The answer type is right, and lists name every item | |

The command exits non-zero below the recall target. The maintenance workflow runs it every
night against production and records the result; the admin Overview shows the latest run
and warns when recall drops by 0.05, MRR drops by 0.1, an important question is missed, or
no run has happened for 3 days. Recorded results are in [project metrics](../metrics.md#answer-quality).

**Every confirmed wrong answer becomes a case in `golden.json`**, so a fix for one pattern
cannot quietly break another.

`manage.py bench_answers` times the pipeline stage by stage on the same questions.

## What CI runs

Every pull request and every push to `main` or `dev` (`.github/workflows/ci.yml`):

| Job | Checks |
|---|---|
| `secrets` | gitleaks over the full history |
| `backend` | Hash-locked install, `pip check`, `ruff`, `pytest` with the coverage floor, migration drift, OpenAPI validation, `check --deploy` with production settings, the emulator tests, `pip-audit` |
| `frontend` | `npm ci`, ESLint with zero warnings, `vitest`, a production build, `npm audit` at high severity |
| `e2e` | The Playwright journeys; the report is uploaded on failure |

All four must pass before a pull request can merge into `main`. Actions are pinned to
commit hashes.

## Checked by hand

Not covered by automated tests, and worth a look after a change nearby: Google sign-in
under the production content security policy, voice input, installing as an app, printing
a chat, and the layout at 360 pixels wide.
