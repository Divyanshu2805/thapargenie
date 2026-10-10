# 0003. Half-precision 768-dimension vectors with HNSW

## Context

The database runs on a small plan with 500 MB of storage. The crawled site alone is
about 12,700 passages and each needs an embedding and an index entry.

## Decision

Embeddings are stored as `halfvec(768)`: 768 dimensions at 16-bit precision, with
an HNSW index (m = 16, ef_construction = 64) using cosine distance. Queries use
`ef_search = 100` and an iterative scan, so the "searchable" filter cannot starve the
result list.

## Consequences

- Half the storage of 32-bit vectors, with no measured loss of recall on the evaluation set.
- `EMBED_DIMENSIONS` is fixed at 768; settings refuse any other value because the columns are that size.
- Changing the embedding model means re-embedding every passage.

## Alternatives considered

- **Full-precision or 1,536-dimension vectors**: two to four times the size for no measured gain here.
- **IVFFlat**: needs training on the data and re-tuning as the corpus grows.
