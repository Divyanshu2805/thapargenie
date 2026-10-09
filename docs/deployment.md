# Deployment

How production is set up, how a release reaches it, and how to rebuild it from nothing.
Where each part runs is in [Architecture](architecture.md#where-it-runs); every variable
is explained in [Configuration](configuration.md). No secret belongs in this file or
anywhere else in the repository.

## Releasing

1. Branch from `dev`, open a pull request into `dev`. CI runs; nothing deploys.
2. Open one release pull request from `dev` into `main` and merge it with a merge commit.
3. When CI passes on `main`:
   - Render deploys the API, if anything under `Backend/` changed.
   - `deploy-frontend.yml` builds the web app and publishes it to Firebase Hosting.
4. Bring `dev` level again: `git switch dev`, `git pull origin main`, `git push`.
5. Check the release: `/health/ready/` answers 200, sign in, ask one question, open
   Admin → Overview.

`main` only accepts pull requests with the `secrets`, `backend`, `frontend` and `e2e`
checks green. It stays the default branch because scheduled workflows run from it.

**Rollback:** Render → the service → Events → Rollback, and Firebase Hosting → Release
history → Rollback. Migrations must stay backwards compatible (add a column as nullable
first, remove it in a later release) so a rollback never needs a schema downgrade.

## The parts

### Database and files (Supabase)

- A project in the same region as the API. Data API off, a private bucket `documents`.
- `DATABASE_URL` is the session pooler connection string. Use the transaction pooler
  (port 6543) with `DATABASE_TRANSACTION_POOLING=true` only above about 2×16 threads.
- After the first `migrate`, `secure_database` turns row-level security on for every
  table and revokes the `anon` and `authenticated` roles. It runs on every deploy.
- Use two secret keys, one for Render and one for GitHub, so either can be rotated alone.

### Sign-in (Firebase Authentication)

- A production project, separate from development. Email/password and Google enabled,
  email-enumeration protection on, a password policy enforced.
- Authorized domains: the production web app's domains only.
- An Admin SDK service account key, used to check for revoked sessions.

### API (Render web service)

| Setting | Value |
|---|---|
| Root directory | `Backend` |
| Build command | `pip install --require-hashes -r requirements.txt && cd backend && python manage.py migrate && python manage.py createcachetable && python manage.py secure_database && python manage.py collectstatic --noinput` |
| Start command | `cd backend && gunicorn backend.wsgi` |
| Health check path | `/health/live/` |
| Auto-Deploy | After CI Checks Pass |
| Secret file | `firebase-admin.json`, with `GOOGLE_APPLICATION_CREDENTIALS` pointing at it |

Environment: everything under *Production only* in [Configuration](configuration.md),
with `APP_ENV=production`, `DJANGO_ADMIN_ENABLED=false` and `LOG_FORMAT=json`.

**Set `GUNICORN_CMD_ARGS` yourself.** Render gives every Python service
`GUNICORN_CMD_ARGS="--preload --access-logfile - --bind=0.0.0.0:10000"`, and gunicorn
lets that variable override `gunicorn.conf.py`. Left alone it turns on gunicorn's own
access log (a second line per request, always from `127.0.0.1`) and loads the app in the
master process before the workers fork, which this app is not written for: connections
and thread pools opened at import would be shared by every worker. Add the variable to
the service's environment with the value `--bind=0.0.0.0:10000`.

**`TRUSTED_PROXY_COUNT`** must equal the number of proxies that add to
`X-Forwarded-For` before the request reaches gunicorn. Too low and the per-address rate
limits on the public endpoints count a proxy's address, shared by everyone. Too high and
a caller can forge the address. Every access-log line ends with `xff=N`, the number of
addresses in that header for an ordinary request: `TRUSTED_PROXY_COUNT` is that `N`,
because each proxy appends one address and the client's is the first of them. On Render
behind its Cloudflare edge `N` is 3.

A free instance sleeps after 15 minutes without traffic and takes up to a minute to wake.
GitHub's scheduler is too irregular to prevent that (`keepalive.yml` is best effort); an
external monitor calling `/health/live/` every 5 minutes, or a paid instance, does.

### Web app (Firebase Hosting)

`deploy-frontend.yml` builds with the `VITE_*` variables of the GitHub `production`
environment and deploys with a service account that can only publish hosting
(`FIREBASE_SERVICE_ACCOUNT`). Headers and the single-page rewrite are in `firebase.json`;
the build adds a Content-Security-Policy from `VITE_API_BASE_URL` and
`VITE_FIREBASE_AUTH_DOMAIN` (`Frontend/csp.config.js`).

A custom domain is a `CNAME` to `<project>.web.app`, unproxied, added under Hosting →
Custom domains. Add the same origin to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
on the API and to Firebase's authorized domains.

### Scheduled jobs (GitHub Actions)

`maintenance.yml` runs against production from `main`: a daily purge of expired data, a
daily search-quality check, a weekly encrypted backup, and a weekly re-check of the web
pages added by URL. Its header lists the secrets
and variables the `production` environment needs. Scheduled runs do nothing until the
repository variable `MAINTENANCE_ENABLED` is `true`; manual runs always go ahead.

## Backups and restore

**Backup:** Sundays 03:30 IST. `pg_dump --format=custom` is piped straight into
[`age`](https://age-encryption.org) and kept as a workflow artifact for 35 days. Only the
public key is in GitHub (`BACKUP_AGE_RECIPIENT`). The private key stays off the
repository and off every server, in two places; without it a backup cannot be read.

**Restore** (target: under 4 hours):

1. Pick the target: a new Supabase project (keeps the broken one for investigation) or
   the existing one.
2. Create the extensions: `create extension if not exists vector; create extension if not exists pg_trgm;`
3. Download the newest artifact from the Maintenance workflow and decrypt it:
   `age --decrypt -i thapargenie-backup.key thapargenie-<stamp>.dump.age > restore.dump`
4. `pg_restore --no-owner --no-privileges --clean --if-exists --dbname "$DATABASE_URL" restore.dump`
5. `manage.py migrate`, `createcachetable`, `secure_database`, then `purge_data --dry-run`
   as a smoke test.
6. Uploaded files are not in the dump. If the bucket was lost, documents keep their
   passages and answers still work; the originals need uploading again.
7. Point `DATABASE_URL` on Render at the restored database, redeploy, check
   `/health/ready/`, sign in and ask a question. Delete `restore.dump`.

Practise this once after launch into a scratch project, then every quarter.

## Staff two-factor sign-in

Staff enter a code from an authenticator app after signing in (`access/two_factor.py`).
Nothing needs configuring: the first time a staff member opens the admin dashboard they
are walked through adding the app and are shown ten backup codes, once.

- **Lost phone:** sign in and use a backup code. With none left, the owner runs
  `python manage.py reset_second_factor --email <address> --reason "<why>"` against
  production, and the staff member sets it up again at their next sign-in. The reset is
  in the audit log.
- **Something is wrong with the step itself:** set `STAFF_TWO_FACTOR_REQUIRED=false` on
  the API to switch it off, and back on once fixed.
- **Rotating `DJANGO_SECRET_KEY`** makes the stored authenticator keys unreadable, so
  every staff member has to be reset and enrol again. Plan for that when rotating it.

## Rebuilding from nothing

1. Supabase: project, bucket, keys (above).
2. Firebase: project, sign-in methods, Admin SDK key, a web app for the `VITE_*` values.
3. Render: the service with its environment and secret file. The first deploy migrates
   the database.
4. Staff: `manage.py invite_identity` and `manage.py grant_firebase_staff` for the first
   administrator; the rest are invited from Admin → Access. Each sets up two-factor on
   their first visit to the dashboard.
5. Knowledge: `manage.py import_crawler_export` for crawled pages (hours, and paid
   embedding calls), or upload documents from Admin → Knowledge. Then `manage.py eval_rag`:
   recall@5 should be at least 0.9.
6. GitHub: the `production` environment, then `MAINTENANCE_ENABLED=true` after one
   manual run of each maintenance job.
7. Web app: run *Deploy frontend* by hand, or merge a release.
