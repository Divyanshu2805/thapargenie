# Definition of done

A change is ready for a pull request when every line that applies is true.

## Always

- [ ] The change does what it set out to do, and you have seen it work: in the browser for
      interface changes, with `manage.py ask --trace` for answer changes.
- [ ] `ruff check Backend/backend` and `npm run lint` pass with nothing reported.
- [ ] `pytest` and `npm test` pass. New behaviour has a test; a fixed bug has a test that
      failed before the fix.
- [ ] No [security guardrail](security-guardrails.md) is weakened.
- [ ] Every doc page the change makes inaccurate is updated in the same pull request.
- [ ] The commit message says what changed, in one line.

## When it applies

| If the change touches | Then also |
|---|---|
| A model | A migration is included, it is backwards compatible, and `makemigrations --check` passes |
| An endpoint | The serializer rejects unknown fields; the [API reference](../api/README.md) is updated; `spectacular --validate` passes |
| A student endpoint | There is a test that another user's id answers 404 |
| An admin change | It goes through a service that writes an audit event |
| Search, prompts or the pipeline | `eval_rag --answers` was run, and recall@5 is still at least 0.9 |
| A wrong answer found in real use | A case is added to `rag/eval/golden.json` |
| A setting | It is in `settings/base.py`, [configuration](../local-development/configuration.md) and, if required, `settings/production.py` and the CI deploy check |
| Stored data | A retention rule exists and the privacy notice mentions it |
| A dependency | The lock file is regenerated with hashes; the licence is permissive; `pip-audit` or `npm audit` is clean |
| The interface | It works by keyboard, at 360 pixels wide, and in both themes |
| The web app bundle | `npm run build` succeeds and the first-screen bundle has not grown without reason |
| A number quoted in the docs | [Project metrics](../metrics.md) and the README are updated |

## Before a release

- [ ] CI is green on `dev`.
- [ ] Migrations in the release are safe to roll back from.
- [ ] After the deploy: `/health/ready/` answers 200, sign in, ask one question, open
      **Admin → Overview**.
