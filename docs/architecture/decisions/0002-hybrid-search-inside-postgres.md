# 0002. Hybrid search inside PostgreSQL

## Context

Students ask in loose language ("hostel fee for girls"), and also with exact tokens
such as course codes (UCS301), hall names and years. Vector search handles the first well
and the second badly; keyword search is the reverse.

## Decision

Both searches run in the one PostgreSQL database: pgvector for similarity and a
generated `tsvector` column for full-text search. The two ranked lists are merged with
reciprocal rank fusion (k = 60), which uses ranks only, so cosine distances and text-rank
scores never need to share a scale.

## Consequences

- One system to run, back up and secure; passages and their vectors change in the same transaction.
- Filters such as "searchable" and "current" are ordinary SQL.
- Search quality is scored nightly against a fixed question set; recall@5 has been between 0.94 and 1.00 in the four production runs recorded in [project metrics](../../metrics.md#answer-quality).
- The keyword query is the slowest part of search, so it runs on its own connection while the phrasings are embedded.

## Alternatives considered

- **A dedicated vector database** (Pinecone, Qdrant): another service, another bill, and a sync problem between it and Postgres.
- **Vector search alone**: misses course codes and proper names.
- **Weighted score blending**: needs the two score scales calibrated against each other, and re-calibrated when either changes.
