# 0002: Shared database tenancy with row-level security

**Status:** accepted

**Context.** Every customer workspace's data must stay private, and a single missed filter must not leak another tenant's data.

**Decision.** There is one shared PostgreSQL schema, and every tenant table carries `workspace_id`. There are three layers of protection:

1. Services filter explicitly by workspace.
2. Session listeners add the workspace filter to every ORM query and refuse cross-workspace writes.
3. PostgreSQL row-level security enforces the same rule for any SQL, including raw queries. It uses `app.workspace_id` and `app.bypass_rls`, both set per transaction.

Cross-tenant system work, such as the dispatcher, webhooks and migrations, opts out explicitly with `system_session`. A session with no workspace scope sees no tenant rows.

**Consequences.**
- The app must not connect as a superuser in production, because superusers bypass row-level security.
- New tenant tables must be added to the row-level security policy list.
- The whole test suite runs under row-level security in CI.
