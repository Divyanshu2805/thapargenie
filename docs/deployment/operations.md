# Operations

Running ThaparGenie in production: what runs on a schedule, what to watch, and what to do
when something goes wrong. Setting it up is in [deployment](README.md).

## Scheduled jobs

`maintenance.yml` runs the code on `main` against production. Scheduled runs do nothing
until the repository variable `MAINTENANCE_ENABLED` is `true`; manual runs from the Actions
tab always go ahead.

| Job | Schedule (IST) | Does |
|---|---|---|
| `eval` | Daily, 02:00 | Scores search quality on the 23 evaluation questions (about 40 model calls) and records it for the Overview. Fails below recall@5 0.9, so GitHub emails the owner |
| `purge` | Daily, 03:00 | Marks documents past their "valid until" date not current, then applies the [retention rules](../schema/README.md#retention) |
| `backup` | Mondays, 03:30 | An encrypted dump of the database, kept as a workflow artifact for 35 days |
| `refresh` | Sundays, 04:00 | Re-reads every web page added by URL and re-processes the ones whose text changed |
| `context-long` | Manual only | Writes context sentences for pages over 150 passages |

GitHub starts scheduled runs late, in practice 2 to 4 hours after the listed time. Each job
has a dry-run variant under *Run workflow*: `purge-dry-run`, `refresh-dry-run`,
`context-long-dry-run`. Jobs never overlap (one concurrency group).

`keepalive.yml` pings `/health/ready/` every 10 minutes from 07:30 to 23:30 IST when the
repository variable `KEEPALIVE_URL` is set. It is best effort; an external monitor is what
actually keeps a free instance awake.

## Backups

`pg_dump --format=custom` is piped straight into [`age`](https://age-encryption.org), so
the dump never touches a disk unencrypted. Only the public key is in GitHub
(`BACKUP_AGE_RECIPIENT`). The private key stays off the repository and off every server, in
two places the owner controls; without it a backup cannot be read. A run fails if the
result is under 1 KB.

Recovery point: up to 7 days on the free database plan. Uploaded files are not in the dump.

### Restore

Target: under 4 hours. These steps are written down but have not yet been exercised end to
end; practise them into a scratch project.

1. Pick the target: a new Supabase project (which keeps the broken one for investigation)
   or the existing one.
2. Create the extensions:
   `create extension if not exists vector; create extension if not exists pg_trgm;`
3. Download the newest artifact from the Maintenance workflow and decrypt it:
   `age --decrypt -i thapargenie-backup.key thapargenie-<stamp>.dump.age > restore.dump`
4. `pg_restore --no-owner --no-privileges --clean --if-exists --dbname "$DATABASE_URL" restore.dump`
5. `manage.py migrate`, `createcachetable`, `secure_database`, then `purge_data --dry-run`
   as a smoke test.
6. If the bucket was lost too, documents keep their passages and answers still work; the
   originals need uploading again.
7. Point `DATABASE_URL` on Render at the restored database, redeploy, check
   `/health/ready/`, sign in and ask a question. Delete `restore.dump`.

## Monitoring

| Signal | Where |
|---|---|
| Is it up | An external monitor on `/health/live/` (the process) and the site, every 5 minutes. `/health/ready/` also checks the database |
| Questions, how answers ended, ratings, latency, cache hits, AI calls against the budget, knowledge base size | **Admin → Overview** |
| Search quality and regressions | The *Answer quality* card on the Overview, from the nightly `eval` |
| Unanswered questions and complaints | **Admin → Knowledge gaps** |
| Errors | The API's logs on Render; Sentry when `SENTRY_DSN` is set |
| Database size, connections, CPU | The Supabase dashboard. The free plan holds 500 MB |
| Model spend | Google AI Studio, with a spend cap set there |
| Failed scheduled jobs | GitHub emails the owner |

### Logs

One line per request under the logger `thapargenie.access`: method, path, status, duration
and `xff=N`. Never the query string or the body. Every line from any logger carries
`request_id` and `user_id` (the numeric id, never the email), and with `LOG_FORMAT=json`
each line is one JSON object. Question text, answers and document content are never
logged. Health checks are not logged.

| Logger | Holds |
|---|---|
| `thapargenie.access` | One line per request |
| `thapargenie.errors` | Every 5xx with its traceback; throttled and refused requests |
| `thapargenie.client` | Errors reported by browsers, with emails and long numbers masked |

Browser errors are logged at warning level, so they appear in the logs but do not open
Sentry issues.

## Runbooks

### A student reports an error

Ask for the time and what they were doing. Search the logs for that minute and a status of
500 or more, take the `request_id`, and follow it across lines and into Sentry. The error
shown in the app carries the same id.

### Documents stuck in queued or processing

Wait 5 minutes: the recovery loop re-queues anything stuck for over 15. If it is still
stuck, look in the logs for `Recovery:` and `Unexpected failure while processing`, or run
`manage.py process_documents` to drain the queue by hand.

### The model provider is down or out of quota

Students see "very busy" or "answer service unavailable", each with a retry, and the
question does not count against their day. Options: wait; raise the spend cap; turn on
maintenance mode with a message; or switch `LLM_PROVIDER` to `openai`. The embedding
provider must stay the same unless the whole corpus is re-embedded
(`process_documents --reembed`).

### Asking pauses for everyone with "very busy"

The day's AI budget is used up. **Admin → Overview** shows calls against the budget; raise
`global_daily_llm_calls` in **Admin → Settings** if the usage is genuine. It resets at
midnight IST.

### Search quality dropped

The Overview warns when recall@5 falls below 0.9 or drops by 0.05, or an important
question is missed. Run `manage.py eval_rag --answers` to see which questions fail, then
`manage.py ask "<question>" --trace` on one. The usual causes: a document was disabled,
deleted or marked not current; a page changed and was re-read; a model name changed.

### Staff two-factor

- **Lost phone:** sign in and use a backup code. With none left, the owner runs
  `python manage.py reset_second_factor --email <address> --reason "<why>"` against
  production; the staff member enrols again at their next sign-in. The reset is audited.
- **The step itself is broken:** set `STAFF_TWO_FACTOR_REQUIRED=false` on the API, and back
  to `true` once fixed.

### A release went wrong

Roll back both parts: Render → Events → Rollback, and Firebase Hosting → Release history →
Rollback. Then fix on a branch and release again.

## Secrets

Rotate at once if one leaks, otherwise yearly.

| Secret | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | It also encrypts staff authenticator keys. After rotating it, reset every staff member with `reset_second_factor`; they enrol again |
| Supabase service keys | Render and GitHub hold separate keys, so each rotates alone |
| Gemini or OpenAI key | Update Render and the GitHub `production` environment |
| Firebase Admin key | Create the new key, deploy it, then delete the old one |
| The backup `age` key | Keep the old private key for as long as backups encrypted with it are kept |

## When to scale

| Symptom | Next step |
|---|---|
| The instance sleeps and the first request waits a minute | A paid instance |
| Answers queue at busy times (time to first word rises) | More threads per worker, with the transaction pooler above 2 × 16; then a larger instance. See [load testing](../load-testing.md#what-each-size-carries) |
| Rate limits must be exact, or there is more than one instance | Move throttle counters to Redis |
| More than about 50 uploads a day, or several instances | A Postgres-backed queue with its own worker for ingestion |
| The database passes about 350 MB, or backups are needed daily | A paid database plan |
| The AI budget is reached on ordinary days | Raise `global_daily_llm_calls` deliberately and the provider's spend cap with it |
