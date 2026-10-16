# LeadsGen

A multi-tenant SaaS for compliant B2B outreach. Teams find leads for a niche, enrich company websites, score leads and write emails from templates or with AI. Emails go out in multi-step sequences, and real replies, bounces and complaints come back in. **A person approves every email before it is sent.**

- **Workspaces:** owner, admin and member roles, invitations, plan limits and usage tracking.
- **Sequences:** follow-ups are drafted automatically when they're due and wait in the approval queue. A reply, bounce or unsubscribe stops the sequence.
- **Approval queue:** split view with keyboard shortcuts, edit, regenerate, and bulk approve or reject. Compliance problems are checked live for each draft.
- **AI drafts** (optional): Groq, OpenAI or Gemini, using the workspace's own key or the platform key.
  - Guardrails: no invented numbers, no links, no hype, length limits.
  - Falls back to the template when a draft fails the guardrails, and says why.
  - Token usage and cost are tracked.
- **Real inbound:** signed webhooks from Resend, SendGrid and Mailgun, or IMAP polling.
  - Replies are matched to the email they answer.
  - Out-of-office and auto-replies are recognised.
  - Hard bounces and complaints suppress the address across the platform.
  - A campaign pauses itself if bounces or complaints spike.
- **Sending pipeline:**
  - Messages outside the sending window are deferred, not failed.
  - Timezone-aware schedules, daily and per-domain limits, and warm-up.
  - Each message is delivered at most once; retries back off.
  - One-click unsubscribe (RFC 8058) and a server-added footer.
- **Deliverability check:** SPF, DKIM, DMARC and MX for your sending domain.

The stack:
- **API** (`services/api`): FastAPI, SQLAlchemy 2, Alembic, Celery and Redis, with PostgreSQL in production.
- **Web app** (`apps/web`): Next.js 15, TanStack Query and Tailwind.
- **Hosting:** Railway; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Compliance rules (enforced in code)

- No LinkedIn automation, no scraping of search engines (only approved search APIs) and robots.txt is respected.
- Nothing is sent without human approval, a lead source and compliance note, a suppression check and an opt-out line.
- Unsubscribing suppresses that address only. Free-mail domains (gmail.com etc.) can't be blocked as a whole.
- Outreach only goes through the workspace's own sending account; the platform mailer is used for account emails only.

See [Agents.md](Agents.md) for the full guidelines.

## Local development

You need Python 3.12+, Node.js 20+ and Redis 7+ (Redis is only needed for background jobs). SQLite is the default database locally; no Docker required.

```bash
cp .env.example .env            # defaults work for local development

# API
cd services/api
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed.py          # optional demo data; prints a one-time demo password
uvicorn app.main:app --reload --port 8000

# Background jobs (separate terminals, from services/api)
celery -A app.core.celery_app worker -l info -Q default,sending,inbound,enrichment
celery -A app.core.celery_app beat -l info

# Web app
cd apps/web
npm install
npm run dev                     # http://localhost:3000, proxies /api to localhost:8000
```

Helper scripts for each process are in [`scripts/`](scripts/) (`dev-api`, `dev-worker`, `dev-beat`, `dev-web`, in PowerShell and bash).

In development, account emails (verification, password reset, invitations) are printed to the API log, because `PLATFORM_EMAIL_PROVIDER=console`. Outreach uses the workspace's sending account. Add a **Mock** sending account in Settings → Providers to try the whole flow without sending real email.

To try AI drafts locally, set `FEATURE_AI_EMAILS=true` and either `PLATFORM_LLM_PROVIDER=mock` or a real provider key. Then turn on AI in Settings → Workspace.

## Tests and checks

```bash
# API (from services/api)
ruff check . && ruff format --check .
mypy app
pytest -q                                    # SQLite
TEST_DATABASE_URL=postgresql://... pytest -q # the same suite on PostgreSQL

# Web app (from apps/web)
npm run lint && npm run typecheck && npm test && npm run build
npm run gen:api   # regenerate TypeScript API types after changing the API
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs all of these, plus:
- the PostgreSQL migration round-trip with `alembic check`
- a check that the generated API types are up to date
- dependency audits

## Project layout

```
services/api/
  app/api/routes/        HTTP endpoints (thin; logic lives in services)
  app/services/          sending, sequences, inbound, llm, approvals, billing, enrichment …
  app/models/            SQLAlchemy models (every tenant row has workspace_id)
  app/workers/           Celery tasks; beat schedule in app/core/celery_app.py
  alembic/versions/      migrations (every schema change has one)
  tests/                 pytest suite (SQLite and PostgreSQL)
apps/web/
  src/app/               pages (App Router)
  src/components/        feature components and the shared DataTable / UI kit
  src/lib/api/           API client, endpoints and generated types
docs/                    deployment and provider setup
```

## Feature flags

New capabilities are dark-launched and off by default:

| Flag | Enables |
|---|---|
| `FEATURE_AI_EMAILS` | AI drafts, AI regeneration, AI reply labelling |
| `FEATURE_INBOUND_WEBHOOKS` | Provider webhooks for replies, bounces and complaints |
| `FEATURE_IMAP` | IMAP inbox polling for replies |

## More documentation

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): Railway services, environment, migrations, backups, health checks.
- [docs/PROVIDERS.md](docs/PROVIDERS.md): setting up sending accounts, webhooks, IMAP, AI and search providers.
