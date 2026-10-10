# 0012. Staff two-factor inside the app

## Context

A stolen staff password would open the knowledge base, the user list and the
settings. Firebase offers multi-factor sign-in only on its paid Identity Platform tier.

## Decision

The second step is built into the API (`access/two_factor.py`): time-based codes
from any authenticator app (RFC 6238), ten single-use backup codes, a lockout after five
wrong codes, and a check that lasts 12 hours for one sign-in. Every admin endpoint requires
it.

## Consequences

- No paid upgrade, and students are unaffected.
- The app key is encrypted with a key derived from `DJANGO_SECRET_KEY`, so rotating that secret means every staff member enrols again.
- Recovery without backup codes needs the owner to run `reset_second_factor`.
- `STAFF_TWO_FACTOR_REQUIRED=false` is an emergency switch.

## Alternatives considered

- **Firebase multi-factor**: managed, but paid and tied to SMS or a platform upgrade.
- **No second factor**: one phished password away from the admin dashboard.
