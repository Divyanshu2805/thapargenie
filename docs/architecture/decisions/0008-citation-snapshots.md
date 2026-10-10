# 0008. Citations stored as snapshots

## Context

Documents are replaced, edited and deleted. An answer given last month must still
show what it was based on.

## Decision

When an answer is saved, each source it was given is copied into `MessageSource`:
title, link, section, pages, a snippet and whether it was cited. The links back to the
passage and document are nullable.

## Consequences

- Old answers stay readable after their documents are gone.
- Share links copy the same snapshot, so a shared answer never changes.
- A snapshot can show a title or link that has since changed; opening the source goes through the live document when it still exists.

## Alternatives considered

- **Foreign keys only**: deleting a document would either be blocked or erase the citations of every answer that used it.
