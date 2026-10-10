# Features

Everything ThaparGenie does, by area, with the limits that apply. The numbers behind the
limits are collected in [project metrics](metrics.md).

## Who uses it

| Role | How they get in | What they can do |
|---|---|---|
| Visitor | Not signed in | Landing page, sign in, register, reset password, the privacy notice, a shared answer |
| Pending user | Signed in, email unverified or account not yet approved | A status screen (verify, pending, denied, suspended), resend verification, sign out |
| Student | Verified email and an approved account | Chat, history, notices, settings, feedback |
| Admin | A student with staff access, granted from the command line only | Everything a student can, plus the admin dashboard after a two-factor step |

## Asking

- **Questions in English or Hinglish**, up to 2,000 characters. Follow-ups such as "and for
  girls?" are understood from the chat.
- **Streamed answers** with a progress line (understanding, searching, reading, writing).
  Stopping keeps what was written and marks it stopped.
- **Citations on every fact.** Each `[n]` opens its source: the official page, or the
  uploaded file through a link that expires after 10 minutes.
- **A check on every figure.** Amounts, years and dates in an answer must appear in a source
  it cites; when one does not, the answer carries a "verify with the official source" note.
- **A freshness line** saying which academic session the sources cover and their latest
  date, with a warning when a source is marked not current.
- **Honest misses.** When the documents do not cover a question, the answer says so and
  points to the office or page to check. It never guesses.
- **Questions it does not search for.** Greetings get a short reply, personal records
  (marks, attendance, dues) are pointed to Webkiosk, off-topic requests are declined, and a
  remark about an earlier answer ("that's wrong", "why didn't you say this before?") is
  answered from the chat itself.
- **"List all" questions** load the whole page the list lives on, so no item is left out.
- **Follow-up suggestions**: up to three, generated only when the student asks for them and
  then kept with the answer.
- **Voice input** through the browser's speech recognition (Chrome and Edge).
- **Starter questions** on an empty chat, set by admins.
- **Personalisation**: an optional campus, programme and year of study, used only when a
  question depends on them.

## Conversations

- History is kept across devices. The sidebar lists pinned chats first, then the most
  recent, 30 at a time.
- **Branches.** Regenerating an answer or editing a question adds a version beside the old
  one; arrows switch between versions.
- Automatic titles, rename, pin, archive and delete.
- **Search** in chat titles and message text, from the sidebar or with
  <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>K</kbd>.
- **Download** a chat as Markdown, or print it (which also saves a PDF).
- **Share an answer** as a public, read-only link that lasts 7 days and can be switched off.
  The link shows the question, the answer and its public sources, and nothing about who
  shared it.
- Thumbs up or down on any answer; a thumbs down takes a reason and a comment.
- A conversation holds up to 200 messages; one answer streams at a time per student.

Keyboard: <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>K</kbd> search,
<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>O</kbd> new chat,
<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>B</kbd> sidebar, <kbd>Esc</kbd> stops an answer.

## Other student pages

- **Notices**: announcements posted by admins, with important ones marked, and a list of
  official documents added in the last 30 days.
- **What can I ask?**: the topics the knowledge base covers, with document counts, what it
  cannot help with, and tips.
- **Feedback**: suggestions and problems about the site itself, with an optional rating and
  a choice about being contacted.
- **Settings**: personalisation, light or dark theme, export every chat as JSON, delete all
  chats, and sign out on all devices.
- **Install as an app** on phones and desktops (a web app manifest; no offline mode).
- **Privacy notice** at `/privacy`: what is stored, why, for how long and who processes it.

## Admin dashboard

Reached at `/admin/`. Every admin request needs staff access and, by default, a code from an
authenticator app after each sign-in.

| Page | What it does |
|---|---|
| Overview | Questions per day, how answers ended, thumbs-up rate, cache hits, latency, AI calls against the daily budget, knowledge base size, documents about to expire, and the nightly search-quality check with regression warnings |
| Feedback | Rated answers with the question, answer and sources under a pseudonym; resolve or dismiss with a note. Site feedback is reviewed here too |
| Knowledge gaps | Questions that got no answer, grouped and counted, and follow-ups in which a student complained about an earlier answer |
| Documents | Upload up to 10 files at once (PDF, Word, Excel, CSV, HTML, text), add a web page by URL or a piece of text; filter, edit details, enable, disable, reprocess, delete; act on up to 100 documents at once; view and edit individual passages |
| Playground | Run a question through the pipeline without saving it and see the analysis, the candidates with their ranks, the sources and the answer |
| Notices | Post, schedule, pin, expire and delete notices; a notice can also be made answerable, which adds it to the knowledge base |
| Users & invites | Approve, suspend or deny accounts with a reason; invite an email so it skips approval |
| Settings | Approval on or off, maintenance mode and message, a banner, the daily question limit, the daily AI budget, reranking, the answer cache, automatic titles and the starter questions |
| Audit log | Who did what, filtered by action, with no question or answer text |

Feedback, knowledge gaps and daily statistics can be downloaded as CSV (up to 5,000 rows).

## Knowledge base

- **Sources**: uploaded files, web pages from allowlisted college domains, typed text, and a
  bulk import of the thapar.edu crawler export.
- **Processing** is automatic: extract text, split into passages, embed, publish. A document
  stays answerable on its old passages while it is reprocessed.
- **Scanned and table-heavy PDFs** are read by the model, page window by page window.
- **Details per document**: category, department, academic session, effective date, a
  "valid until" date and a current flag. After its "valid until" date a document is marked
  not current and ranks lower.
- **Duplicates** are refused by content hash.
- **Web pages added by URL** are re-read every week and re-processed only when their text
  changed.

## Limits

| Limit | Value |
|---|---|
| Questions per student per day | 40 (an admin setting); staff are not limited |
| AI calls per day, everyone together | 5,000 (an admin setting); asking pauses when it is reached |
| Question length | 2,000 characters |
| Messages per conversation | 200 |
| Answers streaming at once | 1 per student |
| Upload size and length | 25 MB and 300 PDF pages per file, 10 files per upload |
| Typed text entry | 100,000 characters |
| Bulk document action | 100 documents |
| Share link | 7 days |
| Chats with no activity | Deleted after 180 days |

Request rate limits are in [errors and rate limits](api/errors-and-rate-limits.md#rate-limits),
and how long each kind of data is kept is in the [data model](schema/README.md#retention).
