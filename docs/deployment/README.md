# Deployment

How production is set up, how a release reaches it, and how to rebuild it from nothing.
Running it day to day (scheduled jobs, backups, monitoring, incidents) is in
[operations](operations.md). No secret belongs in this repository.

| Part | Host | Deploys when |
|---|---|---|
| Web app | Firebase Hosting | CI passes on `main` |
| API | Render web service, Singapore | CI passes on `main` and `Backend/` changed |
| Database and files | Supabase, Singapore | Migrations run in the API's build |
| Sign-in | Firebase Authentication, a production project | Configured by hand |
| Scheduled jobs | GitHub Actions, from `main` | On their schedule |

## Releasing

1. Branch from `dev` and open a pull request into `dev`. CI runs; nothing deploys.
2. Open one release pull request from `dev` into `main` and merge it with a **merge
   commit**. Squashing would split the history of the two branches.
3. When CI passes on `main`:
   - Render deploys the API, if anything under `Backend/` changed.
   - `deploy-frontend.yml` builds the web app from the exact commit CI tested and publishes
     it to Firebase Hosting.
4. Bring `dev` level again: `git switch dev`, `git pull origin main`, `git push`.
5. Check the release: `/health/ready/` answers 200, sign in, ask one question, open
   **Admin → Overview**.

`main` accepts only pull requests with the `secrets`, `backend`, `frontend` and `e2e`
checks green, and no force pushes. It stays the default branch because scheduled workflows
run from it.

**Rollback:** Render → the service → Events → Rollback, and Firebase Hosting → Release
history → Rollback. Migrations stay backwards compatible so a rollback never needs a schema
downgrade. Open browser tabs recover by themselves: a failed chunk load after a deploy
reloads the page once.

## The parts

### Database and files (Supabase)

- A project in the same region as the API. Data API off; a private bucket named `documents`.
- `DATABASE_URL` is the session pooler connection string. Switch to the transaction pooler
  (port 6543) with `DATABASE_TRANSACTION_POOLING=true` only above about 2 workers of 16
  threads.
- After `migrate`, `secure_database` turns on row level security for every table and
  revokes the `anon` and `authenticated` roles. It runs on every deploy.
- Two secret keys, one for Render and one for GitHub, so either can be rotated alone.

### Sign-in (Firebase Authentication)

- A production project, separate from development. Email/password and Google enabled,
  email-enumeration protection on, a password policy enforced.
- Authorized domains: the production web app's domains only.
- An Admin SDK service-account key, used to check for revoked sessions.

### API (Render web service)

| Setting | Value |
|---|---|
| Root directory | `Backend` |
| Build command | `pip install --require-hashes -r requirements.txt && cd backend && python manage.py migrate && python manage.py createcachetable && python manage.py secure_database && python manage.py collectstatic --noinput` |
| Start command | `cd backend && gunicorn backend.wsgi` |
| Health check path | `/health/live/` |
| Auto-Deploy | After CI Checks Pass |
| Secret file | `firebase-admin.json`, with `GOOGLE_APPLICATION_CREDENTIALS` pointing at it |

Environment: everything under *Production only* in
[configuration](../local-development/configuration.md#production-only), with
`APP_ENV=production`, `DJANGO_ADMIN_ENABLED=false` and `LOG_FORMAT=json`.

#### Gunicorn arguments

Render gives every Python service
`GUNICORN_CMD_ARGS="--preload --access-logfile - --bind=0.0.0.0:10000"`, and gunicorn lets
that variable override `gunicorn.conf.py`. Left alone it turns on gunicorn's own access log
(a second line per request, always from `127.0.0.1`) and loads the app in the master
process before the workers fork, which this app is not written for: connections and thread
pools opened at import would be shared by every worker. Set the variable on the service to
`--bind=0.0.0.0:10000`.

#### The proxy count

`TRUSTED_PROXY_COUNT` must equal the number of proxies that add to `X-Forwarded-For`
before a request reaches gunicorn. Too low, and per-address rate limits on the public
endpoints count a proxy's address shared by everyone. Too high, and a caller can forge
their address. Every access-log line ends with `xff=N`, the number of addresses in that
header for an ordinary request; `TRUSTED_PROXY_COUNT` is that `N`. On Render behind its
Cloudflare edge it is 3.

#### Sleeping

A free instance sleeps after 15 minutes without traffic and takes up to a minute to wake.
An external monitor calling `/health/live/` every 5 minutes prevents it; so does a paid
instance. `keepalive.yml` does the same from GitHub, but its scheduler is too irregular to
rely on.

### Web app (Firebase Hosting)

`deploy-frontend.yml` builds with the `VITE_*` variables of the GitHub `production`
environment and deploys with a service account that can only publish hosting
(`FIREBASE_SERVICE_ACCOUNT`). Headers, caching and the single-page rewrite are in
`firebase.json`; the build adds a content security policy from `VITE_API_BASE_URL` and
`VITE_FIREBASE_AUTH_DOMAIN`.

A custom domain is a `CNAME` to `<project>.web.app`, unproxied, added under Hosting →
Custom domains. Add the same origin to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
on the API and to Firebase's authorized domains.

### GitHub

A `production` environment, limited to `main`, holds what the workflows need:

| Workflow | Secrets | Variables |
|---|---|---|
| `deploy-frontend.yml` | `FIREBASE_SERVICE_ACCOUNT` | The seven `VITE_*` values |
| `maintenance.yml` | `DJANGO_SECRET_KEY`, `DATABASE_URL`, `FIREBASE_PROJECT_ID`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `BACKUP_AGE_RECIPIENT` | `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CHAT_MODEL`, `FAST_MODEL`, `EMBED_MODEL` |

Repository variables: `MAINTENANCE_ENABLED=true` switches the scheduled jobs on, and
`KEEPALIVE_URL` switches the keep-alive ping on.

## Rebuilding from nothing

1. **Supabase:** project, bucket and keys, as above.
2. **Firebase:** project, sign-in methods, an Admin SDK key, and a web app for the `VITE_*`
   values.
3. **Render:** the service with its environment and secret file. The first deploy migrates
   the database.
4. **Staff:** `invite_identity` and `grant_firebase_staff` for the first administrator; the
   rest are invited from **Admin → Users & invites**. Each sets up two-factor on their
   first visit to the dashboard.
5. **Knowledge:** `import_crawler_export` for crawled pages (hours, and paid embedding
   calls), or upload documents from **Admin → Documents**. Then `eval_rag`: recall@5 should
   be at least 0.9.
6. **GitHub:** the `production` environment, a manual run of each maintenance job, then
   `MAINTENANCE_ENABLED=true`.
7. **Web app:** run *Deploy frontend* by hand, or merge a release.
8. **Monitoring:** an uptime monitor on `/health/live/` and on the site, and optionally
   `SENTRY_DSN`.

## Sizing

Production runs on a free instance: 2 workers of 8 threads. What that carries, and what
each larger plan adds, was measured and is in [load testing](../load-testing.md).
