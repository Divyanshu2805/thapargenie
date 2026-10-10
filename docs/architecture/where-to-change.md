# Where to change things

The file to open for a given task. Paths under `Backend/backend/` unless they start with
`Frontend/`.

## Answers

| To change | Open |
|---|---|
| How a question is classified or rewritten | `rag/analysis.py` (the prompt and the schema) |
| The fixed replies to greetings, personal-record and off-topic questions | `rag/pipeline.py` (`CANNED`, `NOT_FOUND`) |
| Replies to remarks about the chat itself | `rag/conversation.py` |
| Search: list sizes, fusion, boosts, duplicate removal | `rag/retrieve.py` |
| Abbreviations and synonyms for keyword search | `rag/aliases.py` |
| Reranking thresholds | `rag/rerank.py` |
| How many passages reach the model, and the token budgets | `rag/rerank.py` (`KEEP`), `rag/context.py` |
| The answer prompt and its rules | `rag/prompt.py` |
| What counts as an unsupported figure | `rag/grounding.py` |
| The answer cache: similarity threshold, lifetime, what is stored | `chat/cache.py` |
| Chat titles and the rolling summary | `chat/memory.py` |
| Follow-up suggestions | `chat/suggestions.py` |
| A model provider, retries or fallback | `rag/llm/` (`gemini.py`, `openai_provider.py`, `client.py`) |
| Regression questions for search quality | `rag/eval/golden.json` |

## Chat

| To change | Open |
|---|---|
| Checks before a question is accepted | `chat/answering.py` (`_check_admission`, `start_turn`) |
| What is saved when an answer finishes, stops or fails | `chat/answering.py` (`_finish`, `_fail`, `stream_turn`) |
| Branches and the history sent to the model | `chat/engine.py` |
| Limits on question length and conversation size | `chat/models.py` (constants at the top) |
| Daily limits and usage counters | `chat/quota.py`; the values are in `ChatSettings` |
| Share links | `chat/sharing.py` |
| A student endpoint | `chat/views.py`, `chat/serializers.py`, `chat/urls.py` |
| The event stream | `common/sse.py`; reader in `Frontend/src/lib/sse.js` |

## Knowledge base

| To change | Open |
|---|---|
| A new file type | `knowledge/ingest/filetypes.py`, `knowledge/ingest/extract.py`, `SourceType` in `knowledge/models.py` |
| Passage size, overlap, table handling | `knowledge/ingest/chunk.py` |
| Context sentences | `knowledge/ingest/contextualize.py` |
| The processing steps and their error messages | `knowledge/ingest/pipeline.py` |
| Adding, editing, deleting documents (audited) | `knowledge/services.py` |
| Background processing and recovery | `knowledge/jobs.py` |
| Categories | `Category` in `knowledge/models.py`, then `Frontend/src/features/admin/constants.js` |
| Domains pages may be added from | `INGEST_URL_ALLOWLIST`; the checks are in `common/safe_http.py` |
| Re-reading web pages | `knowledge/refresh.py` |

## Access and admin

| To change | Open |
|---|---|
| Token checks | `api/authentication.py`, `api/firebase.py` (protected: see [conventions](../practices/coding-conventions.md#the-auth-code)) |
| Who gets in without approval | `access/policy.py`, `OPEN_ACCESS_EMAIL_DOMAINS` |
| Approving, suspending, inviting | `access/services.py` |
| Two-factor rules | `access/two_factor.py`, `access/permissions.py` |
| What every admin endpoint requires | `common/admin_api.py` (`AdminAPIView`) |
| Runtime settings admins can edit | `ChatSettings` in `chat/models.py`, `chat/admin_services.py`, `Frontend/src/features/admin/SettingsAdminPage.jsx` |
| Dashboard statistics | `chat/admin_services.py` |
| A rate limit | `common/throttles.py`, the rates in `backend/settings/base.py` |
| What is deleted and when | `retention.py` in each app, `RETENTION_*_DAYS` in settings; update `/privacy` too |

## Web app

| To change | Open |
|---|---|
| Routes | `Frontend/src/App.jsx` |
| The sidebar and app frame | `Frontend/src/components/layout/` |
| How an answer, its sources and its actions look | `Frontend/src/features/chat/Message.jsx`, `sources.jsx`, `Markdown.jsx` |
| Sending a question and reading the stream | `Frontend/src/features/chat/use-ask-stream.js` |
| An API call | `Frontend/src/lib/api/` |
| Error messages and retries for requests | `Frontend/src/lib/http.js` |
| The content security policy | `Frontend/csp.config.js` |
| Response headers and caching for the site | `firebase.json` |
| The privacy notice | `Frontend/src/features/privacy/PrivacyPage.jsx` |

## Operations

| To change | Open |
|---|---|
| CI checks | `.github/workflows/ci.yml` |
| Scheduled jobs | `.github/workflows/maintenance.yml` |
| The frontend deploy | `.github/workflows/deploy-frontend.yml` |
| Server process settings | `gunicorn.conf.py` |
| Settings per environment | `backend/settings/` (`base.py`, `local.py`, `test.py`, `production.py`) |
| Log format and what each line carries | `common/observability.py`, `backend/logging.py` |
