# Known gaps

Answer-quality problems found in real conversations, what causes them and the fix.
All three are fixed in code; what is left is applying gap 3 to the pages already stored
(see "To do on the live data" at the end). Fixed gaps are in the table at the end.

Each gap is a pattern, not a single question: the example is only how it was found.

## Gap 1: questions about the conversation get the greeting

**Found:** 2026-09-28. After two hostel answers, the student asked "why didnt you give thhis
info before then?" and got the canned "Hi! I'm ThaparGenie…" reply.

**Cause:**

- Query analysis ([analysis.py](../Backend/backend/rag/analysis.py)) has no intent for
  messages about the assistant's own earlier answers. "greeting" covers "small talk", so
  the message lands there. Reproduced 3 of 3 runs with the full history.
- For any non-college intent, [pipeline.py](../Backend/backend/rag/pipeline.py) returns
  `CANNED[intent]`, which ignores the history. Even a correct label could not produce a
  sensible reply.

**Also affects:** "why did you say that?", "that's wrong", "you missed X", "explain your
last answer", "are you sure?".

**Fix:**

1. Add a `conversation` intent: questions or complaints about previous answers,
   clarifications, "why did you say X". Answer it with a short LLM call that sees the
   history, with no retrieval, and let it admit what the earlier answer missed.
2. Use `CANNED[GREETING]` only when there is no history. Mid-chat, a greeting is answered by
   the same short history-aware call instead (not treated as a college question: "thanks"
   would otherwise be searched for in the documents). If that call fails, the greeting is
   shown.

## Gap 2: "list all" questions return part of the list

**Found:** 2026-09-28. "What are the boys hostels… give me list of all" named 8 of 10 and
said the rest were not in the sources. Amritam (B), Neeram (D) and Viyat (L) were missing,
and "Hostel L" was listed as if it were a separate hostel.

**Cause:**

- Every boys hostel is on one page ("Boys Hostel", `/students/pages/boys-hostel`), split
  into 21 chunks, about 2 per hall. The answer model sees at most `KEEP = 8` chunks
  ([rerank.py](../Backend/backend/rag/rerank.py)) within `BUDGET_TOKENS = 6000`
  ([context.py](../Backend/backend/rag/context.py)). A 10-item list cannot fit.
- The 8 chunks sent were 0, 4, 8, 10, 12, 16 and 18 of "Boys Hostel", plus chunk 0 of
  "HOSTEL FACILITIES". Chunks 1–3 (Amritam), 6 (Neeram) and 14 (Viyat) were left out.
- Keyword search pulled down the best vector matches. Chunks 1, 13 and 17 were #1–3 in
  vector search, but full-text search missed or barely ranked them, so they fell to
  12th–15th after fusion.
- Nothing in analysis or retrieval treats "list everything" differently from any other
  question.

**Also affects:** "all girls hostels", "all electives in sem 5", "all scholarships",
"every department", "all fee components", and any other complete set spread over many
chunks.

**Fix:** add a `wants_complete_list` flag to the analysis output. When it is set
and several top candidates come from one document (7 of 8 here), load that whole
document, and raise the token budget for this case (the hostel page is about 7.5k tokens).

## Gap 3: chunks lose the section they belong to

**Found:** 2026-09-28, together with gap 2. All 21 "Boys Hostel" chunks have an empty
`heading_path`. A chunk that only says "Hostel L" has no link to "Viyat Hall", and a chunk
that continues a hall's details does not name the hall.

**Also affects:** any long page with repeated subsections, such as faculty lists,
department pages, fee tables split across chunks and per-programme syllabi.

**Fix:** at ingestion ([ingestion.md](ingestion.md)), have an LLM read each
document once and write a short line of context for every chunk ("This chunk is about
Viyat Hall (formerly Hostel L), a boys hostel"). Store it with the chunk text and the
full-text search text; this is contextual retrieval. Old and new names then sit in the
chunk itself, so hand-written aliases (for example hall names in
[aliases.py](../Backend/backend/rag/aliases.py)) are not needed. The cause was that the crawler import never wrote these sentences, and
that the model read only the first 12,000 characters of a page (the Boys Hostel page is
about 30,000). Both are fixed; pages already stored need `contextualize_documents`, which
does not need the export file.

## Flags to add: catching new gaps

The gaps above were found by a student noticing. These signals should surface the next
ones automatically:

| Flag | Where it comes from | What it means |
|---|---|---|
| Complaint follow-up | A `conversation`-intent message | The previous answer failed. Listed with the question before it under Admin → Knowledge gaps → Follow-ups about earlier answers |
| Admits incomplete | The answer says the list or details are incomplete or not fully in the sources | Likely a retrieval limit (gap 2) |
| No answer | `answer_type == no_answer` | Missing content or failed retrieval |
| Ungrounded | The grounding check reports unsupported sentences | Possible hallucination |
| Page at risk | Any document with more than `KEEP` chunks | Gets the whole-page treatment for "list all" questions (gap 2) when most of its chunks are kept; a single query finds them |

Review the flagged conversations regularly, and turn each confirmed failure into a case in
[`rag/eval/golden.json`](../Backend/backend/rag/eval/golden.json). Run the eval on every
change so a fix for one pattern does not break another.

**Regression cases** (in `rag/eval/golden.json`, run by `eval_rag`):

- `hostels-list-all-boys`: "list all boys hostels" must name all 11 hostels: Agira, Amritam,
  Prithvi, Neeram, Vyan, Tejas, Ambaram, Viyat, Anantam, Vyom and Hostel-FRF/G. `eval_rag` reports
  "full lists", and with `--answers` the written answer must name every hall too.
- `hostels-complaint-followup`: the hostel conversation must be recognised as a remark
  about the chat (`intents` in the report), not small talk.

These two only mean something against the production corpus: run `eval_rag --answers` there.

## Fixed

| Gap | Fixed on | Change |
|---|---|---|
| 1. Questions about the conversation get the greeting | 2026-10-05 | New `conversation` question type and a short reply from the chat alone (`rag/conversation.py`); greeting only without history; follow-ups listed for admins |
| 2. "List all" questions return part of the list | 2026-10-05 | `wants_complete_list`; the whole page is loaded with a 12,000-token budget (`rag/context.py`) |
| 3. Chunks lose the section they belong to | 2026-10-05 | Crawler import can write context sentences; the model reads up to 60,000 characters; `contextualize_documents` adds them to stored pages |

## Applied to the live data (2026-10-06)

- `contextualize_documents` ran on production: 652 documents (4,646 chunks, about 1,060
  fast-model calls) got context sentences. 669 already had them and 21 pages were skipped
  as too long (over 150 chunks). It met Gemini 429 rate limits on the way; the client's
  retries absorbed them and it finished in one run.
- `eval_rag --answers` afterwards: recall@5 1.00, recall@10 1.00, MRR 0.97, in sources
  1.00, full lists 1.00, intents 1.00, answers 0.96 (102 model calls).
- "list all boys hostels" on the site now names all ten halls with their former hostel
  letters, cited to the one Boys Hostel page.

## Still open

- The 21 pages with more than 150 chunks have no context sentences. Raise
  `CONTEXTUALIZE_MAX_CHUNKS` or process them in parts if questions about them fail.
- In the eval run, `admissions-status-2026-27` scored WRONG (answer type `no_answer`) although
  search found the page at rank 1. Asked again with `manage.py ask`, it answered and was
  grounded ("applications are now closed", from admission.thapar.edu), so this is run-to-run
  variation in the model, not a change from the work above. If it fails again in the nightly
  eval, look at the answer text.
- In the same run `academic-calendar-first-year-2026-27` was flagged UNGROUNDED, wrongly: the
  calendar table keeps the month and the day range in separate columns ("Sept" and "31-4")
  and the answer wrote "31 Aug - 4 Sep", so the six dates that span two months were not found
  as written. The grounding check now reads a month plus a day range on one table row as
  the dates it implies (`range_dates` in `rag/grounding.py`). Re-run the calendar question
  with `manage.py ask` on production to confirm it is grounded.
