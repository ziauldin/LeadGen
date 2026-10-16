# Contributing

Thanks for helping improve LeadsGen. This guide covers how to get set up and what a good change looks like.

## Setup

The quickest way is `docker compose up --build`; see the [README](README.md). For native development, follow the README's *Local development* section.

## Making a change

1. Branch from `main`, for example `feat/inbox-snooze` or `fix/unsubscribe-redirect`.
2. Keep business logic in `services/api/app/services/` and keep routes thin. Raise `AppError` subclasses for expected errors.
3. Any schema change needs an Alembic migration (`alembic revision -m "..."`), and `alembic check` must be clean. If a migration moves data, test it with legacy rows (see `tests/test_migrations.py`).
4. New tenant tables use the `TenantScoped` mixin and must be added to the row-level security table list (see [ADR 0002](docs/adr/0002-tenancy.md)).
5. After changing the API, run `npm run gen:api` in `apps/web` and commit the regenerated types.
6. Add tests: pytest for the API, Vitest for components, and Playwright for important user journeys.
7. Run `make lint test`, or the equivalent commands, before pushing.

## Commit messages

Write short, plain sentences that say what changed, for example "Add snooze to the unified inbox". release-please builds the changelog from merged pull requests. Prefix with `feat:`, `fix:` or `chore:` when you want the change grouped in the release notes.

## Compliance rules

These are not optional; see [Agents.md](Agents.md):
- No LinkedIn automation.
- No scraping of search engines.
- No sending without human approval.
- Always run the suppression check and include an opt-out line.
