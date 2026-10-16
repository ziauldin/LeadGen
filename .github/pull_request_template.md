## What and why

<!-- What does this change, and why is it needed? Link the issue if there is one. -->

## How it was tested

- [ ] `pytest` (and on PostgreSQL if it touches queries or migrations)
- [ ] `npm run lint && npm run typecheck && npm test`
- [ ] Tried it in the app

## Checklist

- [ ] Every schema change has an Alembic migration (`alembic check` is clean)
- [ ] API changes: `npm run gen:api` was run and the types committed
- [ ] New tenant data uses `TenantScoped` and goes through the workspace scope
- [ ] No secrets, personal data or real customer data in code, tests or logs
- [ ] Docs updated (README / docs/) if behaviour or configuration changed
