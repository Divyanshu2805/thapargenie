# Architecture decisions

Why the system is shaped the way it is. Each record states the situation, the choice, what follows from it and what was turned down.

| # | Decision |
|---|---|
| [0001](0001-django-and-firebase-identity.md) | Django REST Framework with Firebase identity |
| [0002](0002-hybrid-search-inside-postgres.md) | Hybrid search inside PostgreSQL |
| [0003](0003-half-precision-vectors-with-hnsw.md) | Half-precision 768-dimension vectors with HNSW |
| [0004](0004-server-sent-events-over-fetch.md) | Server-sent events over fetch |
| [0005](0005-in-process-background-work.md) | Background work in the web process, with state in the database |
| [0006](0006-model-reads-difficult-pdfs.md) | The model reads scanned and table-heavy PDFs |
| [0007](0007-messages-as-a-tree.md) | Conversations as a tree of messages |
| [0008](0008-citation-snapshots.md) | Citations stored as snapshots |
| [0009](0009-no-supabase-auth-or-rest-api.md) | Supabase as plain PostgreSQL and storage only |
| [0010](0010-model-provider-interface.md) | A provider interface for the model |
| [0011](0011-rate-limit-counters-in-process-memory.md) | Rate-limit counters in process memory |
| [0012](0012-staff-two-factor-in-the-app.md) | Staff two-factor inside the app |
| [0013](0013-revocation-check-cached-for-students.md) | Revocation check cached for students |

A new record is added when a choice would surprise someone reading the code, or when it trades one property for another on purpose.
