# Architecture decision records

Short records of significant decisions: the context, what was decided and its consequences. Add a new numbered file for each new decision, and don't edit accepted ones; supersede them with a new record instead.

| # | Decision |
|---|---|
| [0001](0001-modular-monolith.md) | One FastAPI modular monolith with Celery workers |
| [0002](0002-tenancy.md) | Shared database with `workspace_id`, ORM filters and PostgreSQL row-level security |
| [0003](0003-human-approval.md) | Every outreach email needs human approval |
| [0004](0004-cookie-sessions-via-proxy.md) | First-party refresh cookie through a Next.js `/api` proxy |
| [0005](0005-generated-api-types.md) | Frontend API types generated from OpenAPI |
