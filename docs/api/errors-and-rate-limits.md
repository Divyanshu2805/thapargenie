# Errors and rate limits

## The error envelope

Every error from the API has the same shape:

```json
{
  "error": {
    "code": "daily_quota_exceeded",
    "message": "You've reached today's question limit. It resets at midnight.",
    "request_id": "0b9c2c0e-…"
  }
}
```

| Field | |
|---|---|
| `code` | A stable identifier to branch on. Never changes with wording |
| `message` | A sentence that can be shown to the user. Never contains internals |
| `request_id` | The id on every log line for this request |
| `fields` | Validation errors only: `{field: [messages]}` |
| `retry_after_seconds` | Rate limits only; the same value as the `Retry-After` header |

A 500 always reads `internal_error` with a generic message; the traceback goes to the logs
under the same `request_id`.

During an answer stream, a failure arrives as an `error` event instead:
`{"code": …, "message": …, "retryable": true}`.

## Codes

### Signing in

| Status | Code | Meaning |
|---|---|---|
| 401 | `not_authenticated` | No token was sent |
| 401 | `invalid_bearer`, `invalid_identity_token` | The header or the token is malformed or fails verification |
| 401 | `expired_identity_token` | The token is past its expiry; refresh and retry |
| 401 | `revoked_identity_token` | The session was signed out everywhere, or revoked in Firebase |
| 401 | `disabled_identity` | The account is disabled |
| 403 | `email_verification_required` | The email address is not verified |
| 403 | `eligibility_required` | The account is pending, denied or suspended |
| 403 | `identity_review_required` | The identity clashes with an existing account; an admin must look |
| 403 | `recent_auth_required` | The action needs a sign-in from the last 5 minutes |
| 503 | `identity_service_unavailable` | Firebase could not be reached |

### Staff

| Status | Code | Meaning |
|---|---|---|
| 403 | `permission_denied` | Not staff |
| 403 | `second_factor_setup_required` | Staff, but no authenticator app enrolled yet |
| 403 | `second_factor_required` | Enter a code for this sign-in |
| 400 | `second_factor_invalid_code` | Wrong code |
| 429 | `second_factor_locked` | Five wrong codes; wait five minutes |
| 409 | `second_factor_already_set_up`, `second_factor_setup_not_started` | Enrolment was already finished, or was never started |
| 409 | `second_factor_reset_required` | The stored key can no longer be read; the owner must reset it |

### Chat

| Status | Code | Meaning |
|---|---|---|
| 429 | `daily_quota_exceeded` | Today's question limit is used up |
| 409 | `conversation_busy` | An answer is still streaming for this student |
| 409 | `conversation_full` | The conversation holds 200 messages |
| 400 | `invalid_parent` | That message cannot be edited or regenerated |
| 503 | `maintenance` | Maintenance mode is on |
| 503 | `service_busy` | The day's AI budget is used up, or the provider's quota is |
| 503 | `llm_unavailable` | The model could not be reached (stream `error` event) |
| 400 | `suggestions_unavailable` | Follow-ups exist only for completed, answered replies |
| 503 | `suggestions_failed` | The model call for follow-ups failed |
| 503 | `source_unavailable` | A link to the source file could not be made |

### Knowledge base (admin)

| Status | Code | Meaning |
|---|---|---|
| 400 | `unsupported_file` | Not a supported type, empty, damaged or encrypted |
| 413 | `file_too_large` | Over the size limit |
| 400 | `too_many_files` | More than 10 in one upload |
| 400 | `url_not_allowed` | Not HTTPS, not on the allowlist, or resolves to a private address |
| 409 | `invalid_transition` | The document is not in a state that allows the action |
| 503 | `storage_unavailable`, `llm_unavailable` | A dependency is down |

### Access (admin)

| Status | Code | Meaning |
|---|---|---|
| 409 | `invitation_exists` | The email is already invited |
| 409 | `invitation_used` | The invitation was accepted; suspend the user instead |
| 409 | `invalid_state` | That eligibility state cannot be set |
| 409 | `own_account`, `staff_account` | Admins cannot change their own access or another staff member's |

### General

| Status | Code |
|---|---|
| 400 | `invalid` (validation, with `fields`), `parse_error` |
| 404 | `not_found` (also returned for another user's resource) |
| 405 | `method_not_allowed` |
| 429 | `throttled` (a rate limit, with `retry_after_seconds`) |
| 500 | `internal_error` |

## Rate limits

Counted per signed-in user, or per client address when nobody is signed in. Each is an
environment variable (`THROTTLE_*`).

| Scope | Limit | Applies to |
|---|---|---|
| `user` | 120 / minute | Every request |
| `ask` | 6 / minute | Asking and regenerating |
| `suggest` | 10 / minute | Follow-up suggestions |
| `export` | 5 / hour | Exporting all my chats |
| `site_feedback` | 5 / hour | Sending site feedback |
| `shared_view` | 60 / minute per address | Opening a shared answer |
| `client_error` | 20 / minute | Browser error reports |
| `admin_write` | 30 / minute | Admin requests that change something; reads are not counted |
| `admin_export` | 30 / hour | CSV downloads |

Counters live in each worker's memory, so with two workers a rate can be used up to twice
over ([ADR 0011](../architecture/decisions/0011-rate-limit-counters-in-process-memory.md)).
These limits are exact, because they are enforced in the database:

| Limit | Value |
|---|---|
| Questions per student per day | 40, resets at midnight IST |
| AI calls per day, everyone together | 5,000 |
| Answers streaming at once | 1 per student |
| Messages per conversation | 200 |
