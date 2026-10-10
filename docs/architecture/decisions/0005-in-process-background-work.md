# 0005. Background work in the web process, with state in the database

## Context

Documents need processing after upload, and each answer triggers a title and a
summary. The hosting budget is one small web instance: no separate worker and no queue
service.

## Decision

Background work runs on small thread pools inside each web process. All state
lives in the database: a document row is claimed with a single `UPDATE`, and a recovery
loop in every process re-queues anything left queued or stuck, every 5 minutes.

## Consequences

- No Redis, no Celery, nothing extra to deploy or pay for.
- A restart loses no work: claimed-but-unfinished documents are picked up again after 15 minutes.
- Running several workers is safe, because only one can claim a row.
- Heavy ingestion competes with requests for CPU on the same instance.
- Title and summary jobs are optional and bounded: under load the queue drops them instead of growing.

## Alternatives considered

- **Celery with Redis**: the standard answer, and two more services to run.
- **A Postgres-backed queue with a worker process**: the next step if uploads pass about 50 a day or the API runs on several instances.
