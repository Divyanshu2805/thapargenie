# Security

If you find a security problem, please don't open a public issue. Email the maintainer
instead, with steps to reproduce, and give a reasonable time to fix it before sharing it.

## How the app protects data

- Every API request carries a Firebase token. Its expiry is checked each time. Firebase
  confirms the signature and that the account is not disabled or revoked on every request
  for staff, and at most once a minute for students. Accounts must have a verified email
  and be approved. Admin endpoints need staff, and deletes need a recent sign-in.
- Students only ever see their own chats; any other id looks like a missing one (404).
- Uploaded files sit in a private bucket and are opened through short-lived signed links.
- Web pages can only be added from allowlisted domains, and every redirect is checked.
- Admins see feedback under a pseudonym, never the student's email, unless the student
  agreed to be contacted.
- The audit log stores metadata only. Logs have tokens and keys redacted.
- Old data is deleted on a schedule; see [docs/database.md](docs/database.md).
