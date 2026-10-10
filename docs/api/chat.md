# Chat API

Endpoints for signed-in students, under `/api/v1/`. Unless noted, each needs a verified
email and an approved account, and returns only the caller's own data: another student's id
answers 404.

## Account

| Method | Path | |
|---|---|---|
| GET | `me/` | Who is signed in: `uid`, `email`, `email_verified`, `eligibility_state`, `onboarding_status`, `is_staff` and `preferences`. Answers any signed-in user, so pending users can see their status |
| PATCH | `me/` | Set `campus`, `program` or `academic_year` (year of study); answers the same body as `GET` |
| POST | `me/revoke-sessions/` | Sign out on all devices. Needs a recent sign-in |
| GET | `me/export/` | Every chat as a JSON download. 5 an hour |

`onboarding_status` is one of `email_verification_required`, `approval_pending`, `ready`,
`access_denied` or `access_suspended`.

## App state

| Method | Path | |
|---|---|---|
| GET | `app-config/` | `banner`, `maintenance`, `maintenance_message`, `starter_questions`, `daily_limit`, `remaining_today`, `latest_notice_at` and `important_notice` |
| GET | `coverage/` | Topics the knowledge base covers, with document counts and the latest update per topic |

## Conversations

| Method | Path | |
|---|---|---|
| GET | `conversations/` | Newest first, 30 a page. Filters: `archived`, `pinned`, `q` |
| POST | `conversations/` | Start one. `title` is optional |
| DELETE | `conversations/` | Delete all my chats. Needs a recent sign-in |
| GET | `conversations/<id>/` | One conversation |
| PATCH | `conversations/<id>/` | `title`, `is_pinned`, `is_archived`, or `current_leaf_id` to switch branch |
| DELETE | `conversations/<id>/` | Delete it, with its messages, sources and feedback |
| GET | `conversations/<id>/messages/` | The messages on the current branch, each with `sources`, `feedback`, `suggestions` and `siblings` |

`q` searches titles and the text of every message (at least 2 characters). Matches carry a
`match` object with a snippet.

### A message

```json
{
  "id": "…", "parent_id": "…", "role": "assistant",
  "content": "The hostel fee is Rs 1,20,000 per year [1].",
  "status": "complete",
  "answer_type": "answered",
  "grounded": true,
  "error_code": null,
  "created_at": "2026-10-09T08:15:00+00:00",
  "sources": [{
    "position": 1, "source_id": "…", "title": "Fee structure 2026-27",
    "url": "https://www.thapar.edu/…", "heading_path": "Hostel fee",
    "page_start": 3, "page_end": 3, "academic_year": "2026-27",
    "effective_date": "2026-06-01", "is_current": true,
    "category": "fees_scholarships", "snippet": "…", "cited": true
  }],
  "feedback": null,
  "suggestions": [],
  "siblings": {"index": 0, "count": 1, "ids": ["…"]}
}
```

| Field | Values |
|---|---|
| `status` | `complete`, `streaming`, `stopped`, `failed` |
| `answer_type` | `answered`, `no_answer`, `smalltalk`, `conversation`, `out_of_scope`, `personal_record`, `cached`, `error`; `null` on questions |
| `grounded` | `true` when every figure was found in a cited source, `false` when one was not, `null` when the check does not apply |

A reply that did not find an answer lists only the sources it cited.

## Asking

| Method | Path | |
|---|---|---|
| POST | `conversations/<id>/messages/` | Ask a question. Streams the answer |
| POST | `messages/<id>/regenerate/` | A new version of an answer. Streams |

Body for asking:

| Field | |
|---|---|
| `content` | The question, up to 2,000 characters |
| `client_request_id` | A UUID, required. Retrying with the same id replays the earlier result and never creates a second question |
| `edit_of` | Optional id of an earlier question: the new question becomes a sibling of it, starting a new branch |

Regenerating takes only `client_request_id`. Both count against the daily question limit
and the 6-a-minute ask limit.

Send `Accept: text/event-stream, application/json`. Refusals before the stream starts
(`daily_quota_exceeded`, `conversation_busy`, `conversation_full`, `maintenance`,
`service_busy`) come back as ordinary JSON errors.

### Streaming

The response is `text/event-stream`. Each event is `event: <name>` and `data: <json>`.
Comment lines (`: ping`) arrive every 15 seconds while nothing else does.

| Event | Data | When |
|---|---|---|
| `meta` | `conversation_id`, `user_message_id`, `assistant_message_id`, `regenerated`, `remaining_today` | First. The question is already saved |
| `status` | `stage`: `understanding`, `searching`, `reading`, `writing`; sometimes `detail` | As work moves on |
| `sources` | `sources`: the numbered sources | Before the answer text |
| `delta` | `text`: the next piece of the answer | Many times |
| `done` | `message`: the saved answer in full; `remaining_today` | Last, on success |
| `error` | `code`, `message`, `retryable` | Last, on failure. The question is given back to the daily count |

Closing the connection stops the answer; what was written is kept with `status: stopped`.

## After an answer

| Method | Path | |
|---|---|---|
| PUT | `messages/<id>/feedback/` | `rating` 1 or -1; with -1, an optional `reason` (`incorrect`, `outdated`, `incomplete`, `irrelevant`, `unclear`, `other`) and `comment`. A thumbs down removes the answer from the cache |
| DELETE | `messages/<id>/feedback/` | Remove my rating |
| POST | `messages/<id>/suggestions/` | Up to 3 follow-up questions. One model call the first time, then stored. 10 a minute |
| GET | `messages/<id>/share/` | The active share link, if any |
| POST | `messages/<id>/share/` | Create (or return) a public link valid for 7 days |
| DELETE | `messages/<id>/share/` | Switch the link off |
| GET | `sources/<id>/open/` | `{"url": …}`: the official page, or a signed link to the uploaded file valid for 10 minutes |

## Public

| Method | Path | |
|---|---|---|
| GET | `shared/<token>/` | A shared answer: question, answer, sources with public links, expiry. No sign-in. 60 a minute per address. Unknown, expired and switched-off links all answer 404 |

## Notices and feedback

| Method | Path | |
|---|---|---|
| GET | `notices/` | Published notices, pinned first then newest, up to 100. Optional `category` |
| GET | `notices/official/` | Official documents added recently. `days` from 1 to 90, default 30; up to 30 |
| GET | `notices/official/<id>/open/` | A link to one of those documents |
| GET | `site-feedback/` | My last 20 pieces of feedback about the site, with their review status |
| POST | `site-feedback/` | `kind` (`suggestion`, `problem`, `answers`, `other`), `message` (10 to 2,000 characters), optional `rating` 1 to 5, `page`, `contact_ok`. 5 an hour |
