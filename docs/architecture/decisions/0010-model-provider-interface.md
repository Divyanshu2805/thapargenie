# 0010. A provider interface for the model

## Context

Model names, prices and quotas change often, and tests must not call a paid API.

## Decision

`rag/llm/base.py` defines a small interface: embed, generate, stream and read a
PDF. `rag/llm/client.py` adds retries, fallback from the chat model to the fast model,
batching and usage counting on top of any provider. Gemini and OpenAI adapters exist, and
model names come from the environment.

## Consequences

- Switching provider or model is configuration, not code.
- Tests use a fake provider; end-to-end tests and load tests use a deterministic offline one, which production settings refuse.
- Nothing outside `rag/llm` imports a vendor SDK.
- Switching the embedding provider means re-embedding the corpus.

## Alternatives considered

- **Calling one SDK directly**: less code, and every prompt site tied to one vendor.
- **A framework such as LangChain**: far more surface than four methods need.
