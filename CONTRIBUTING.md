# Contributing to ThaparGenie

## Before you start

- Get the app running locally: [local development](docs/local-development/README.md).
- Skim the [architecture overview](docs/architecture/README.md) to find which app owns the
  behaviour you are changing, and [where to change things](docs/architecture/where-to-change.md)
  to find the file.
- Read the [security guardrails](docs/practices/security-guardrails.md). A change that
  weakens one is not accepted as a workaround; raise the problem instead.

## Workflow

1. Branch from an up-to-date `dev`: `feat/…`, `fix/…`, `perf/…` or `docs/…`.
2. Make the change, with tests.
3. Run the checks below.
4. Open a pull request into `dev`. CI must be green.

`main` is production. It changes only through a release pull request from `dev`, merged
with a merge commit; merging deploys the API and the web app. Never push to `main`
directly. See [deployment](docs/deployment/README.md#releasing).

## Checks

```bash
# from the repository root, with `docker compose up -d db` running
ruff check Backend/backend
pytest --cov --cov-fail-under=80
python Backend/backend/manage.py makemigrations --check --dry-run

cd Frontend
npm run lint
npm test
npm run build
```

A change to search, prompts or the answer pipeline also runs
`python manage.py eval_rag --answers`; recall@5 must stay at or above 0.9.

The full checklist is the [definition of done](docs/practices/definition-of-done.md), and
what each suite covers is in [testing](docs/practices/testing.md).

## Conventions

- **Code style**: see [coding conventions](docs/practices/coding-conventions.md). In short:
  views validate and delegate, audited writes go through `services.py`, input serializers
  reject unknown fields, and every student query is scoped to the caller.
- **The sign-in code** (`api/`, `userauths/`, `src/auth`, `src/views/auth`,
  `src/utils/apiClient.js`, `auth.js`, `session.js`) is changed only on purpose. Propose
  the change first.
- **Secrets** never enter the repository. `.env` files are ignored; `.env.example` holds
  placeholders.
- **Docs**: a change that makes any page in `docs/` inaccurate updates it in the same pull
  request.
- **Wrong answers** found in real use become questions in
  `Backend/backend/rag/eval/golden.json`.

## Commit messages

One line, imperative, sentence case, saying what changed:

```
Add two-factor sign-in for staff
Limit open access to thapar.edu addresses
Hide references on not-found answers
```

One concern per commit.

## Known pitfalls

Several things in this stack fail quietly: an embedding call that merges a list into one
vector, a stream refused before the view runs, a setting a connection pooler drops. If
something "should work" and does not, check [known pitfalls](docs/practices/gotchas.md)
first.
