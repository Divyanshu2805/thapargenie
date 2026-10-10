# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Report it privately through
GitHub: on the repository's **Security** tab, choose **Report a vulnerability**.

Include what you found, how to reproduce it, and the impact you expect. You will get an
acknowledgement, and a fix or mitigation will be agreed with you before any details are
made public.

Please do not test against other people's accounts or data on the live site, and do not
run automated scanners or load against it.

## Scope

This repository's code and deployment configuration, and the live app at
[thapargenie.divyanshuagrahari.dev](https://thapargenie.divyanshuagrahari.dev).

The identifiers in `.github/workflows/`, `.firebaserc.example` and the `VITE_*` variables
are public by design and are not secrets. The credentials in `compose.yml`, the CI workflow
and `loadtest/` belong to throwaway local databases.

## How the app protects data

- **Every request is authenticated** with a Firebase ID token, verified on the server and
  mapped to one account by Firebase UID. An account needs a verified email and approval.
- **Students reach only their own chats.** Any other id answers "not found".
- **Staff need a second step**: a code from an authenticator app after each sign-in, asked
  again after 12 hours. Staff access itself is granted only from the command line.
- **Irreversible actions need a recent sign-in.**
- **Uploaded files are private** and opened through signed links that expire in 10 minutes.
- **Pages are fetched only from allowlisted domains**, with every redirect and resolved
  address checked.
- **The model never receives a student's identity**, and question text is never logged.
- **Admins see feedback under a pseudonym**, unless the student agreed to be contacted.
- **Old data is deleted on a schedule**, and students can export or delete their chats.

The full picture is in the [security model](docs/architecture/security-model.md); the rules
every change must respect are in the
[security guardrails](docs/practices/security-guardrails.md); and what the design accepts
is in [known gaps](docs/known-gaps/README.md).
