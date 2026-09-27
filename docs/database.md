# Database

PostgreSQL with the `vector` and `pg_trgm` extensions (created by the first `common`
migration).

## Main tables

| Table | |
|---|---|
| `userauths_user`, `userauths_profile` | Accounts (mapped by Firebase UID) and the optional student profile. |
| `userauths_identityinvitation` | Emails allowed in without waiting for approval. |
| `api_auditevent` | Who did what: metadata only, never question or answer text. |
| `knowledge_document` | One row per document, with its status and metadata. |
| `knowledge_chunk` | The searchable pieces: text, a 768-dimension `halfvec` embedding (HNSW index) and a generated full-text column. |
| `chat_conversation`, `chat_message` | Chats. Messages form a tree through `parent` so answers can have versions. |
| `chat_messagesource` | A snapshot of each cited source, readable even after the document is deleted. |
| `chat_feedback`, `chat_sitefeedback` | Answer ratings and feedback about the site. |
| `chat_answertrace` | How an answer was produced, for admins. |
| `chat_answercache` | Cached answers to first questions. |
| `chat_usagedaily` | Counters per user per day for limits and stats. |
| `chat_chatsettings` | One row of runtime settings. |
| `chat_sharedanswer` | Public share links. |
| `notices_notice` | Notices posted by admins. |
| `rag_evalrun` | Results of the search quality check. |

## Keeping data

`python manage.py purge_data` applies the retention rules: chats with no activity for 180
days, answer traces after 30 days, usage counters after about 13 months, audit events and
site feedback after a year, notices a year after they expire, failed documents after 30 days,
and share links 30 days after they end. Every setting is a `RETENTION_*_DAYS` variable.
`--dry-run` shows what would go.

`python manage.py secure_database` turns on row level security for every app table, so the
Supabase REST API cannot read them; the app connects as the owner and is not affected.
