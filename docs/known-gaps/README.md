# Known gaps

What ThaparGenie does not do, what it trades away on purpose, and the answer-quality
problems found so far with their fixes.

## Targets not met

### Speed

The first word of an answer was meant to arrive within 3 seconds. In production it takes
about 8 (median of four timed questions on 2026-10-09: 8, 14, 8, 8 s); full answers take
10.2 s at the median and 16.2 s at the 95th percentile. The time goes to steps that run
before any text can appear: question analysis, embedding, search, and the answer model's
own reasoning, which alone waits several seconds.

Reaching 3 seconds needs a faster answer model, or searching on the raw question while
analysis runs. Neither is built. Answers served from the cache are immediate.

### Restore never drilled

The backup runs weekly and the restore steps are written down, but no restore has been
carried out end to end.

## Constraints and trade-offs

| Constraint | Effect | Way out |
|---|---|---|
| A free API instance with 16 worker threads | About 8 answers stream at full speed at once; more slow down. It sleeps after 15 idle minutes unless pinged | More threads, then a larger instance. Measured in [load testing](../load-testing.md) |
| Rate limits counted per worker | A limit can be used up to twice over with two workers | Redis, once there is more than one instance |
| Background work runs in the web process | Heavy ingestion competes with requests; fine at a few uploads a day | A database-backed queue with its own worker |
| Weekly backups | Up to 7 days of data could be lost; uploaded files are not in the dump | A paid database plan with daily backups |
| One region | The API and database are both in Singapore; there is no failover | |
| A daily AI budget | Asking pauses for everyone once 5,000 model calls are made in a day | Raise it in admin settings, with the provider's spend cap |
| The model reads scanned PDFs | Extraction of scans and complex tables is good, not exact, and not repeatable run to run | Admins can view and correct every passage |
| A student revoked in the Firebase console keeps access for up to 60 seconds | Accepted to avoid a Firebase call on every request | `FIREBASE_REVOCATION_CACHE_SECONDS=0` |
| Crawled pages are a snapshot | Pages from the crawler import change only when a new export is imported. Pages added by URL are re-read weekly | |

## Not built

- **Personal records.** Marks, attendance and fee dues live behind the Webkiosk login;
  such questions are pointed there.
- **Languages** other than English and Hinglish, and a translated interface.
- **Offline use and push notifications.** The app installs to a home screen but needs a
  connection.
- **Students uploading their own documents.**
- **Email**: no digests, no "your question now has an answer".
- **College single sign-on.** Sign-in is email and password or Google.
- **A staging environment.** Changes go from local and CI straight to production.
- **Per-device session lists.** "Sign out on all devices" ends every session at once.
- **Automated faithfulness scoring.** Search quality is scored nightly; whether an answer
  follows from its sources is checked for figures only, by the grounding check.

## Answer quality

Problems found in real conversations. Each is a pattern, not one question: the example is
only how it was found. All three below are fixed and have regression questions in
`rag/eval/golden.json`.

### 1. Remarks about the chat got the greeting

**Found** 2026-09-28. After two hostel answers a student asked "why didn't you give this
info before then?" and received the canned "Hi! I'm ThaparGenie…" reply.

**Cause.** Query analysis had no category for messages about the assistant's own earlier
answers, so they fell into "greeting", and every non-college category returned a fixed
reply that ignored the chat.

**Fix** (2026-10-05). A `conversation` intent, answered by one short model call that sees
the chat and searches nothing (`rag/conversation.py`). It may admit what an earlier answer
missed but adds no new facts. The fixed greeting is used only when there is no chat yet.
Admins see these follow-ups, with the question before them, under **Knowledge gaps**.

### 2. "List all" questions returned part of the list

**Found** 2026-09-28. "List all boys hostels" named 8 of 10 and said the rest were not in
the sources.

**Cause.** All the hostels are on one page, split into 21 passages. The answer model saw
the best 8 passages within a 6,000-token budget, so a ten-item list could not fit. Nothing
treated "list everything" differently from any other question.

**Fix** (2026-10-05). Analysis returns `wants_complete_list`. When it is set and most of
the kept passages come from one document, the whole document is loaded under a 12,000-token
budget (`rag/context.py`).

### 3. Passages lost the section they belonged to

**Found** 2026-09-28, with the previous one. A passage that said only "Hostel L" had no
link to "Viyat Hall", its current name, so keyword search missed it.

**Cause.** The crawler import wrote no context sentences, and the model that writes them
read only the first 12,000 characters of a page.

**Fix** (2026-10-05). The import can write context sentences; the model reads up to 60,000
characters and longer pages in windows; `contextualize_documents` adds them to stored
pages. Applied to production on 2026-10-06 (652 documents, 4,646 passages, about 1,060
model calls), and to the 21 longest pages on 2026-10-09.

### Open

- **Run-to-run variation.** The nightly check on 2026-10-10 ranked the page for
  `jee-cutoff-first-round-2026` 18th, after two nights at rank 1 with no change to the
  code. Query analysis is a model call, and a different rewrite can move a result. If it
  repeats, compare the rewritten question between a passing and a failing night
  (`manage.py eval_rag --case jee-cutoff-first-round-2026`).
- **Tiny passages from short scans** can rank above fuller ones.

## Catching the next one

| Signal | Where | Suggests |
|---|---|---|
| A follow-up complaining about an answer | **Knowledge gaps → Follow-ups about earlier answers** | The previous answer failed |
| `no_answer` | **Knowledge gaps** | Missing content, or search missed it |
| A thumbs down with a reason | **Feedback** | Wrong, outdated or incomplete |
| The "verify" note on an answer (`grounded = false`) | The answer itself, and the trace | A figure not found in the cited sources |
| A regression warning | **Overview → Answer quality** | A change hurt search |

Each confirmed failure becomes a question in `rag/eval/golden.json`, and the evaluation
runs on every change to search or prompts.
