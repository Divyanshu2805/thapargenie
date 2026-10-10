# 0013. Revocation check cached for students

## Context

Asking Firebase whether a session was revoked costs about 300 ms on every request.
Skipping it means a disabled account keeps working until its token expires, up to an hour.

## Decision

A token Firebase has just confirmed is trusted for 60 seconds without asking
again, for students only. Staff are checked with Firebase on every request.

## Consequences

- Most student requests skip the round trip.
- A student disabled or revoked in the Firebase console keeps access for at most 60 seconds.
- Suspension, approval and "sign out on all devices" are checked in the app's own database on every request and are not delayed.
- `FIREBASE_REVOCATION_CACHE_SECONDS` sets the window, from 0 (always ask) to 300.

## Alternatives considered

- **Always ask**: exact, and slow on every request.
- **Never ask**: fast, and up to an hour of access after a revocation.
