# Admin API

Everything under `/api/v1/admin/`. Every endpoint requires:

1. a verified, approved account with staff access;
2. the two-factor step passed for this sign-in (except `two-factor/…` itself);
3. for every `DELETE`, and for a bulk delete, a sign-in from the last 5 minutes.

Writes are limited to 30 a minute per admin and each one is recorded in the audit log.
List filters are validated: an unknown value answers 400 with the filter named in `fields`.

## Two-factor

Until the step is passed, every other admin endpoint answers 403 with
`second_factor_setup_required` (not enrolled yet) or `second_factor_required`.

| Method | Path | |
|---|---|---|
| GET | `two-factor/` | `required`, `enrolled`, `verified`, `recovery_codes_left`, `session_hours` |
| POST | `two-factor/setup/` | A new key and its `otpauth://` URI, to add to an authenticator app |
| POST | `two-factor/confirm/` | `code`: finishes enrolment and returns ten backup codes, once |
| POST | `two-factor/verify/` | `code` or `recovery_code`: passes the step for this sign-in |
| POST | `two-factor/recovery-codes/` | Replaces the backup codes. Needs the step passed and a recent sign-in |

## Documents

| Method | Path | |
|---|---|---|
| GET | `documents/` | 50 a page. Filters: `status`, `category`, `source_type`, `validity` (`expiring`, `expired`), `details` (`missing_session`), `q` (title) |
| POST | `documents/` | Upload up to 10 files (multipart, 25 MB and 300 pages each). Answers per file: created, duplicate, or why it was refused |
| POST | `documents/url/` | Add a web page from an allowlisted domain |
| POST | `documents/text/` | Add a piece of text or an FAQ entry, up to 100,000 characters |
| GET | `documents/<id>/` | One document with its status, counts and details |
| PATCH | `documents/<id>/` | Edit details |
| DELETE | `documents/<id>/` | Delete it, its passages and its stored file |
| POST | `documents/<id>/reprocess/` | Extract, chunk and embed again; optional `parser` |
| POST | `documents/<id>/enable/`, `disable/` | Put it in or take it out of search |
| GET | `documents/<id>/file/` | A signed link to the original, valid for 10 minutes |
| GET | `documents/<id>/chunks/` | Its passages |
| PATCH | `chunks/<id>/` | Edit a passage's text or heading; that passage is re-embedded |
| DELETE | `chunks/<id>/` | Remove a passage |
| POST | `documents/bulk/` | `action` (`update`, `enable`, `disable`, `reprocess`, `delete`) on up to 100 `ids`, with `changes` or per-document `changes_by_id` for `update` |
| GET | `documents/ids/` | Every id matching the list filters, up to 2,000, for "select all matching" |
| POST | `documents/suggest-details/` | Suggested academic session and issue date for documents, by rules; with `ai=true`, the fast model for at most 20 |

Details a document accepts: `title`, `category`, `department`, `academic_year` (`YYYY-YY`),
`effective_date`, `valid_until`, `is_current`, `source_url` (HTTPS), `parser` (`auto`,
`fast`, `smart`) and `contextualize`.

A document's `status` is `queued`, `processing`, `ready`, `failed` or `disabled`.

## Insight

| Method | Path | |
|---|---|---|
| GET | `stats/` | The Overview numbers for `range` `7d` or `30d`: questions per day, how answers ended, ratings, cache hits, latency, AI usage against the budget, knowledge base size, documents near expiry, and the search-quality summary |
| GET | `gaps/` | Unanswered questions, grouped and counted, up to 100 |
| GET | `complaints/` | Follow-ups about an earlier answer, each with the question before it, up to 50 |
| GET | `feedback/` | Rated answers. Filters: `review_status`, `rating`, `answer_type`, `reason` |
| PATCH | `feedback/<id>/` | `review_status` (`open`, `resolved`, `dismissed`) and `admin_note` |
| GET | `site-feedback/` | Feedback about the site. Filters: `review_status`, `kind` |
| PATCH | `site-feedback/<id>/` | Review it the same way |
| GET | `stats/export/`, `gaps/export/`, `feedback/export/` | The same as CSV, up to 5,000 rows. 30 an hour |
| POST | `playground/` | Run `query` (with optional `history`, up to 8 messages) through the pipeline without saving a chat. Returns the analysis, candidates with ranks, sources, the answer and timings |

Students appear under a pseudonym in feedback and gaps. Site feedback shows an email only
when the student set `contact_ok`.

## Settings

| Method | Path | |
|---|---|---|
| GET | `settings/` | The current values |
| PATCH | `settings/` | Any of the fields below. Changes apply within a minute |

| Field | Default | |
|---|---|---|
| `require_approval` | `true` | Off lets verified addresses on the allowed domains in without an admin |
| `maintenance_mode`, `maintenance_message` | off | Pauses asking for students |
| `banner_text` | empty | Shown on every student screen |
| `daily_question_limit` | 40 | Per student per day |
| `global_daily_llm_calls` | 5,000 | AI calls per day across everyone |
| `rerank_enabled` | `false` | The reranking step |
| `cache_enabled` | `true` | The answer cache |
| `contextualize_default` | `false` | Context sentences for newly added documents |
| `auto_title_enabled` | `true` | Model-written chat titles |
| `starter_questions` | 6 | Up to 8 `{category, text}` pairs |

## Users and audit

| Method | Path | |
|---|---|---|
| GET | `users/` | Filters: `q` (email or name), `eligibility_state` |
| PATCH | `users/<id>/` | `eligibility_state` (`approved`, `suspended`, `denied`) with a `reason`. Not for staff accounts or your own |
| GET | `invitations/` | Filter: `q` |
| POST | `invitations/` | Invite an `email`, with an optional `expires_at` |
| DELETE | `invitations/<id>/` | Revoke an unused invitation |
| GET | `audit-log/` | Filters: `action` (exact, or a prefix ending in `.`), `resource_type`, `resource_id` |

## Notices

| Method | Path | |
|---|---|---|
| GET | `notices/` | Filters: `state` (`published`, `scheduled`, `draft`, `expired`), `q` |
| POST | `notices/` | `title`, `body`, `category`, `importance`, `is_pinned`, `is_draft`, `publish_at`, `expires_at`, `link_url`, `answerable` |
| GET, PATCH | `notices/<id>/` | One notice |
| DELETE | `notices/<id>/` | Delete it; `delete_document=true` also removes its knowledge-base copy |

An `answerable` notice is copied into the knowledge base while it is published, so students
can ask about it. The copy follows the notice's schedule and expiry.
