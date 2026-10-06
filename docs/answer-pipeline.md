# Answer pipeline

`rag/pipeline.py` turns a question into events: `status`, `sources`, `delta` and `done`.
It does not save anything; `chat/answering.py` does that.

## Steps

1. **Cache** (first question of a chat only). The question is embedded and looked up in
   `AnswerCache`. A close enough match (cosine ≥ 0.97) returns the stored answer and
   sources straight away. Only grounded, cited answers are stored, the cache is cleared
   whenever the knowledge base changes, and a thumbs down removes an entry.
2. **Analysis** (`rag/analysis.py`). One call to the fast model returns the intent
   (college question, greeting, a remark about the chat itself, personal record or
   off-topic), a standalone English version of the question, up to two other phrasings,
   keywords, hints like the academic year, and whether the student wants a complete list
   ("list all hostels"). Greetings with no chat before them and off-topic questions get a
   fixed reply. Mid-chat, thanks and remarks about an earlier answer ("why didn't you tell
   me before?", "that's wrong") get a short reply from one model call that sees the chat
   and searches nothing (`rag/conversation.py`); it may admit what the earlier answer
   missed but adds no new facts. If the analysis call fails, the raw question is used.
3. **Search** (`rag/retrieve.py`). Each phrasing is searched with pgvector; the keywords
   (with Thapar abbreviations expanded, see `rag/aliases.py`) go through Postgres full-text
   search at the same time. Reciprocal rank fusion merges the lists, small boosts favour
   current documents and matching sessions, and near-duplicate passages are dropped.
4. **Rerank** (off by default, a setting). The fast model scores the top 15 passages and
   the best 8 are kept.
5. **Sources** (`rag/context.py`). Passages from the same document that sit next to each
   other become one numbered source, and a passage cut off mid-table gets its neighbour.
   Sources stop at about 6,000 tokens. For a "list all" question, when most of the kept
   passages come from one page, the whole page is loaded and the limit is 12,000 tokens, so
   no item is left out; a page too big for that adds its other retrieved passages instead.
6. **Answer**. The chat model streams the answer from the sources only, citing them as
   `[n]`. The last few messages and a rolling summary of older ones give it context.
7. **Grounding** (`rag/grounding.py`). Every figure in the answer (amounts, years, dates)
   must appear in a source it cites. If one doesn't, the answer is flagged for the student.

## Measuring it

`rag/eval/golden.json` holds questions with the pages that should be found.
`python manage.py eval_rag` reports recall@5, recall@10 and MRR; `bench_answers` times the
whole pipeline. `python manage.py ask "question" --trace` shows every step for one question.
