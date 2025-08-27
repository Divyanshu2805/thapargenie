# Answer pipeline

`rag/pipeline.py` turns a question into events: `status`, `sources`, `delta` and `done`.
It does not save anything; `chat/answering.py` does that.

## Steps

1. **Cache** (first question of a chat only). The question is embedded and looked up in
   `AnswerCache`. A close enough match (cosine ≥ 0.97) returns the stored answer and
   sources straight away. Only grounded, cited answers are stored, the cache is cleared
   whenever the knowledge base changes, and a thumbs down removes an entry.
2. **Analysis** (`rag/analysis.py`). One call to the fast model returns the intent
   (college question, greeting, personal record or off-topic), a standalone English version
   of the question, up to two other phrasings, keywords and hints like the academic year.
   Greetings and off-topic questions get a fixed reply. If the call fails, the raw question
   is used.
3. **Search** (`rag/retrieve.py`). Each phrasing is searched with pgvector; the keywords
   (with Thapar abbreviations expanded, see `rag/aliases.py`) go through Postgres full-text
   search at the same time. Reciprocal rank fusion merges the lists, small boosts favour
   current documents and matching sessions, and near-duplicate passages are dropped.
4. **Rerank** (off by default, a setting). The fast model scores the top 15 passages and
   the best 8 are kept.
5. **Sources** (`rag/context.py`). Passages from the same document that sit next to each
   other become one numbered source, and a passage cut off mid-table gets its neighbour.
   Sources stop at about 6,000 tokens.
6. **Answer**. The chat model streams the answer from the sources only, citing them as
   `[n]`. The last few messages and a rolling summary of older ones give it context.
7. **Grounding** (`rag/grounding.py`). Every figure in the answer (amounts, years, dates)
   must appear in a source it cites. If one doesn't, the answer is flagged for the student.

## Measuring it

`rag/eval/golden.json` holds questions with the pages that should be found.
`python manage.py eval_rag` reports recall@5, recall@10 and MRR; `bench_answers` times the
whole pipeline. `python manage.py ask "question" --trace` shows every step for one question.
