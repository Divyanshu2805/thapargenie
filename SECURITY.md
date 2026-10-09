# Security

If you find a security problem, please don't open a public issue. Email the maintainer
instead, with steps to reproduce, and give a reasonable time to fix it before sharing it.

## How the app protects data

- Every API request carries a Firebase token. Its expiry is checked each time. Firebase
  confirms the signature and that the account is not disabled or revoked on every request
  for staff, and at most once a minute for students. Accounts must have a verified email
  and be approved. Admin endpoints need staff, and deletes need a recent sign-in.
- Staff also pass a second step: a code from an authenticator app, entered after each
  sign-in and asked again after 12 hours. The admin API refuses everything until then.
  The app's key is stored encrypted and backup codes as hashes; five wrong codes lock
  the step for five minutes.
- With admin approval switched off, only verified `thapar.edu` addresses get in without
  an admin; any other address still waits to be approved or invited.
- Students only ever see their own chats; any other id looks like a missing one (404).
- Uploaded files sit in a private bucket and are opened through short-lived signed links.
- Web pages can only be added from allowlisted domains, and every redirect is checked.
- Admins see feedback under a pseudonym, never the student's email, unless the student
  agreed to be contacted.
- The audit log stores metadata only. Logs have tokens and keys redacted.
- Old data is deleted on a schedule; see [docs/database.md](docs/database.md).
