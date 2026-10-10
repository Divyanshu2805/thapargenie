# Known pitfalls

Things in this stack that fail quietly or cost time the first time. If something "should
work" and does not, look here first.

## Models and embeddings

- **`gemini-embedding-2` turns a list of strings into one vector.** Send one `Content` per
  text (`rag/llm/gemini.py` does). It also takes the task as a text prefix, not `task_type`;
  only the older `-001` model takes `task_type`.
- **Keep one model client per process.** A discarded `genai.Client` closes its connection
  pool and later calls fail. `rag.llm.provider()` caches it.
- **Default thinking makes the first word wait about 11 seconds.** `ANSWER_THINKING=low`
  brings it to about 8. `minimal` is accepted only by the fast model.
- **The reranker's scores vary from run to run**; the same passage has scored 3, 6 and 8.
  That is why the two best fused candidates are dropped only at a score of 0, and why
  reranking is off by default.
- **The institute's name is noise in keyword search.** Every document mentions it, so it is
  stripped from the query (`rag/retrieve.py`).
- **Calendar tables put the month and the day range in different columns** ("Sept" and
  "31-4"). An answer writes "31 Aug to 4 Sep", which never appears in the source as text;
  `rag/grounding.py: range_dates` derives the dates a row implies so the check does not
  flag them.
- **PDF extraction mangles dashes.** "2026–27" can arrive as "2026�27"; the grounding check
  and the session parser accept both.

## Streaming

- **An ask request must also accept `application/json`.** DRF negotiates the response type
  against its renderers before the view runs and refuses `text/event-stream` alone with a
  406.
- **A worker thread cannot see a test's transaction.** Tests stream inline
  (`SSE_INLINE=True`) and search on the request thread (`RETRIEVE_PARALLEL=False`).
- **Close a streamed test response** with `response._iterator.close()`, or the generator's
  cleanup never runs.
- **The `done` event is sent after the answer is saved and the follow-up work is queued**,
  so a client that disconnects right after it loses nothing.

## Django and PostgreSQL

- **Supabase's pooler drops the `options` startup parameter**, so `statement_timeout` set
  there never reached the server. The timeouts are set with a `SET` on each new connection
  instead (`common/db.py`).
- **The transaction pooler keeps no session state.** With `DATABASE_TRANSACTION_POOLING` on,
  session settings are skipped, server-side cursors are off, prepared statements are off,
  and vector search sets its own settings per query.
- **`run_before` in `common/0001_extensions` names `knowledge/0001_initial`.** If that
  migration is ever regenerated, comment the line out first.
- **`NullIf(field, '')` reads `''` as a field name.** Use
  `Value('', output_field=TextField())`.
- **`extra={...}` with a key already on the log record raises `KeyError`.** Request and
  user ids are added by a handler filter for that reason.
- **An approved user needs `eligibility_approved_at`.** A check constraint enforces it;
  fixtures and factories must set both.
- **DRF copies throttle rates onto the classes at import.** Changing the setting later
  does nothing.

## Hosting

- **Render sets `GUNICORN_CMD_ARGS`**, which overrides `gunicorn.conf.py`: it turns on a
  second access log and preloads the app in the master process, which this app is not
  written for. The service sets the variable itself to `--bind=0.0.0.0:10000`.
- **`TRUSTED_PROXY_COUNT` must match the proxies in front of the API.** Too low and
  per-address limits count a shared proxy; too high and a client can forge its address.
  The access log's `xff=` number is the right value.
- **A free instance sleeps after 15 minutes idle** and takes up to a minute to wake. An
  external monitor pinging `/health/live/` every 5 minutes prevents it; GitHub's scheduler
  is too irregular to rely on.
- **Uptime monitors usually send `HEAD`.** The health views accept it.
- **Supabase Storage lists one folder level per call**, a page at a time, with folders
  marked by a null id. The orphan sweep keeps paging while a page is full.

## Testing

- **End-to-end tests need a production build.** The dev server's StrictMode runs effects
  twice, and the verify-email page then burns its one-time code on the first run.
- **With `force_authenticate`, the user object is not reloaded between requests.** Call
  `refresh_from_db()`.
- **`assertLogs` captures with its own handler**, so handler filters (request context,
  redaction) do not apply to what it records.
- **To assert "no row lock"**, capture queries and look for `FOR UPDATE`.

## Tooling

- **The `.gitignore` files under `Frontend/` use CRLF line endings.** A scripted
  replacement that assumes `\n` silently changes nothing.
- **On Windows, a Playwright `webServer` command runs under `cmd.exe`**: relative paths to
  executables need backslashes.
- **Custom request headers must be listed in `CORS_ALLOW_HEADERS`** or the browser's
  preflight fails. `x-request-id` is.
