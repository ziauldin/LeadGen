# LeadsGen API

FastAPI backend for LeadsGen. See the [root README](../../README.md) for setup and [docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md) for production.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A app.core.celery_app worker -l info -Q default,sending,inbound,enrichment
celery -A app.core.celery_app beat -l info
```

## Conventions

- **Tenancy:** every tenant table has `workspace_id` (the `TenantScoped` mixin). Routes resolve the workspace with `get_current_workspace` (the `X-Workspace-Id` header). The session listeners in `app/core/tenancy.py` add the workspace filter and stamp new rows. System jobs opt out explicitly with `system_session`.
- **Business logic** lives in `app/services/`; routes stay thin. Expected errors raise `AppError` subclasses (`app/core/errors.py`), which map to HTTP responses in one place.
- **Every schema change** has an Alembic migration. `alembic check` must report no drift on SQLite and PostgreSQL.
- **Email status changes** go through `app/services/sending/state.py`. Sends go through the gate (`gate.py`, which decides allow, defer or block) and the dispatcher.
- **Tests:**
  - `pytest -q` runs on in-memory SQLite.
  - Set `TEST_DATABASE_URL` to run the same suite on PostgreSQL.
  - Background jobs run eagerly in tests.
  - Outgoing email goes to in-memory outboxes: `MOCK_OUTBOX` for outreach and `OUTBOX` for platform email.
  - The mock LLM takes queued responses (`MOCK_LLM_QUEUE`).

`python scripts/export_openapi.py <file>` writes the OpenAPI schema that the web app's TypeScript types are generated from.
