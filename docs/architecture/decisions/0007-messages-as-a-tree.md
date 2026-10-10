# 0007. Conversations as a tree of messages

## Context

Students regenerate answers and edit earlier questions. Overwriting loses the
earlier version; copying the conversation wastes storage and breaks links.

## Decision

Each message points to its parent. Regenerating adds a sibling answer, editing
adds a sibling question, and the conversation stores the leaf of the branch on screen. The
history sent to the model is the chain from the root to that leaf.

## Consequences

- Nothing a student saw is ever lost, and versions can be flipped through.
- A conversation is capped at 200 messages, so the whole tree loads in one query and is walked in memory.
- The rolling summary records which message it covers and is ignored on a branch that does not contain it.

## Alternatives considered

- **A flat list with overwrite**: simple, and loses history.
- **A new conversation per edit**: clutters the sidebar and breaks follow-up context.
