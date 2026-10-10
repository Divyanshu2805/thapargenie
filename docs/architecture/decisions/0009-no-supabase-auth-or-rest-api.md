# 0009. Supabase as plain PostgreSQL and storage only

## Context

Supabase offers its own sign-in and a REST API that exposes tables directly to
browsers, guarded by row level security policies.

## Decision

Neither is used. The API connects as the database owner; the Data API is switched
off; and `secure_database` turns on row level security with no policies on every table and
revokes the `anon` and `authenticated` roles, on every deploy. The storage bucket is
private and reached only with the service key.

## Consequences

- One place decides who may read what: the Django API.
- A leaked public Supabase key reads nothing.
- The database stays portable: it is ordinary PostgreSQL with two extensions.

## Alternatives considered

- **Supabase Auth with row level security policies**: authorization split between SQL policies and application code, and a second identity system beside Firebase.
