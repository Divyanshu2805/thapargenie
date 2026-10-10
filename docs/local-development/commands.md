# Commands

## Every day

```bash
docker compose up -d db                        # the local database
cd Backend/backend && python manage.py runserver   # API on :8000
cd Frontend && npm run dev                     # web app on :5173
```

## Checks before a push

CI runs all of these; running them first saves a round trip.

```bash
# from the repository root, with the database running
ruff check Backend/backend
pytest --cov --cov-fail-under=80
python Backend/backend/manage.py makemigrations --check --dry-run
python Backend/backend/manage.py spectacular --validate --fail-on-warn --file /dev/null

cd Frontend
npm run lint
npm test
npm run build
npx knip            # unused files, exports and dependencies
```

One test file or one test:

```bash
pytest Backend/backend/rag/tests/test_retrieval.py -k fusion
npx vitest run src/features/chat/thread.test.js
```

End-to-end tests need the Firebase CLI and build the app first:

```bash
cd Frontend
npx playwright install chromium
npx firebase-tools emulators:exec --config ../firebase.json --only auth --project demo-thapargenie "npm run test:e2e"
```

## Management commands

Run from `Backend/backend` as `python manage.py <command>`.

### Access

| Command | Does |
|---|---|
| `invite_identity <email> --actor-email <superuser>` | Invites an address, so it is approved on its first verified sign-in |
| `grant_firebase_staff --firebase-uid <uid> --actor-email <superuser> --reason "…"` | Makes a signed-in user staff. `--revoke` removes it. The only way to change staff access |
| `reset_second_factor --email <address> --reason "…"` | Removes a staff member's two-factor setup, so they enrol again |

### Knowledge base

| Command | Does |
|---|---|
| `import_crawler_export <folder>` | Imports `chunks.jsonl.gz` from the crawler. Resumable. `--dry-run`, `--limit N`, `--categories a,b`, `--include-review`, `--contextualize` |
| `process_documents` | Processes everything queued now and re-queues stuck documents. `--reembed` queues every ready document for re-embedding first |
| `contextualize_documents` | Writes context sentences for stored passages that have none and re-embeds them. `--dry-run`, `--limit N`, `--title text`, `--include-long` |
| `refresh_web_pages` | Re-reads pages added by URL and re-processes those whose text changed. `--dry-run`, `--limit N`, `--delay seconds` |
| `expire_documents` | Marks documents past their "valid until" date as not current. `--dry-run` |

### Answers

| Command | Does |
|---|---|
| `ask "<question>"` | Runs one question through the pipeline and prints the answer. `--trace` shows the analysis, candidates and timings; `--rerank` turns reranking on |
| `eval_rag` | Scores search against `rag/eval/golden.json`: recall@5, recall@10, MRR. Exits non-zero under `--min-recall` (0.9). `--answers` also writes and checks answers, `--case <id>` runs one, `--record manual` saves the run for the Overview |
| `bench_answers` | Times the pipeline per stage on the evaluation questions: p50 and p90, and time to the first word. `--limit N`, `--warmup N` |

### Operations

| Command | Does |
|---|---|
| `purge_data` | Applies the retention rules. `--dry-run`, `--skip-storage` |
| `secure_database` | Turns on row level security for every table and revokes Supabase's API roles. `--check` only reports |
| `createcachetable` | Creates the table behind the default cache. Needed once per database |
| `seed_e2e` | Creates the end-to-end test accounts in the Auth emulator and one searchable document. Emulator only |

## Dependencies

Python dependencies are locked with hashes. After editing `requirements.in` or
`requirements-dev.in`:

```bash
cd Backend
uv pip compile requirements.in --python-version 3.13 --generate-hashes --universal -o requirements.txt
uv pip compile requirements-dev.in --python-version 3.13 --generate-hashes --universal -o requirements-dev.txt
```

Frontend versions are pinned exactly in `package.json`; install with `npm ci`.
