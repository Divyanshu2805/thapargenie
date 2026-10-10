# 0011. Rate-limit counters in process memory

## Context

Django REST Framework keeps throttle counters in the default cache, which here is
a database table. That cost 6 SQL statements on every request, about 360 ms from the API's
region.

## Decision

Throttles use a separate in-memory cache per worker process. The default cache
stays in the database for what must be shared.

## Consequences

- Six statements fewer on every request.
- Each worker counts alone, so with 2 workers a rate limit can be used up to twice over, and counts reset when a worker restarts.
- The limits that must be exact are not throttles: the daily question limit and the one-stream rule are enforced in the database.

## Alternatives considered

- **Redis**: exact and shared, and the right move once the API runs on more than one instance.
- **Keeping the database cache**: exact, and too slow.
