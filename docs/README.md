# ThaparGenie Documentation

Everything about how ThaparGenie works, how it is built, and how to run and change it.
Start with the section that matches what you are trying to do.

## Getting started

- [Features](features.md): everything the app does, by area, with its limits.
- [Local development](local-development/README.md): prerequisites, setup, configuration,
  commands, troubleshooting.
- [Tech stack](tech-stack.md): the frameworks, models and services in use.

## Understanding the system

- [Architecture](architecture/README.md): the parts, the backend apps, where it runs.
- [Asking a question](architecture/flows/asking-a-question.md): from a request to a stored,
  cited answer.
- [Ingestion](architecture/flows/ingestion.md): from an upload to searchable passages.
- [Sign-in and access](architecture/flows/authentication.md): tokens, approval, staff and
  two-factor.
- [Security model](architecture/security-model.md): the boundaries and where each is
  enforced.
- [Architecture decisions](architecture/decisions/README.md): why the system is shaped the
  way it is (thirteen records).
- [Data model](schema/README.md): the tables, indexes, conventions and retention.

## Reference

- [API reference](api/README.md): [chat](api/chat.md), [admin](api/admin.md), and
  [errors and rate limits](api/errors-and-rate-limits.md).
- [Configuration](local-development/configuration.md): every environment variable.
- [Project metrics](metrics.md): measured quality, answer quality, speed and scale, and
  how to re-check each.
- [Load testing](load-testing.md): what one instance carries, per size.
- [Known gaps](known-gaps/README.md): targets not met, trade-offs, what is not built, and
  the answer-quality problems found so far.
- [Where to change things](architecture/where-to-change.md): the file to open for a task.

## Contributing

- [`CONTRIBUTING.md`](../CONTRIBUTING.md): the workflow, the checks and the commit style.
- [Engineering practices](practices/README.md): conventions, testing, security guardrails,
  known pitfalls, definition of done.
- [`SECURITY.md`](../SECURITY.md): reporting a vulnerability.

## Running in production

- [Deployment](deployment/README.md): each hosted part, releasing, rolling back, rebuilding
  from nothing.
- [Operations](deployment/operations.md): scheduled jobs, backups and restore, monitoring,
  runbooks, secrets, when to scale.

## Keeping these docs accurate

These pages describe the system as it is now. A change that makes any of them inaccurate
updates them in the same pull request, and a number that changes is updated in
[project metrics](metrics.md) and the README together.
