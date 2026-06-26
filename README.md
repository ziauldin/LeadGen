# LeadsGen

Compliant B2B lead-intelligence and outreach workflow system. Choose a niche, generate search queries, collect public lead URLs through approved providers, enrich company websites, score leads, generate personalised emails, run controlled campaigns, and track replies.

**Local development is native only** — SQLite, Redis, Python venv, and npm. No Docker required.

## Prerequisites

| Tool       | Version | Purpose              |
|------------|---------|----------------------|
| Python     | 3.12+   | FastAPI backend      |
| Node.js    | 20+     | Next.js frontend     |
| Redis      | 7+      | Celery broker (optional for API-only dev) |

SQLite is bundled with Python — no separate database install required. The app creates `services/api/data/leadsgen.db` automatically.

### Windows setup

- **Redis** (for Celery): [Redis for Windows](https://github.com/microsoftarchive/redis/releases), WSL, or Memurai

```powershell
redis-cli ping
# Expected: PONG
```

## Quick start

### 1. Environment

```powershell
copy .env.example .env
# Edit SECRET_KEY and other values as needed (DATABASE_URL is optional — SQLite is the default)
```

For the frontend, create `apps/web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Backend

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts\seed.py
```

Start services (separate terminals):

```powershell
# API
uvicorn app.main:app --reload --port 8000

# Celery worker (enrichment, campaigns, replies)
celery -A app.core.celery_app worker -l info

# Celery beat (optional scheduled jobs)
celery -A app.core.celery_app beat -l info
```

Helper scripts from repo root:

```powershell
.\scripts\verify-setup.ps1
.\scripts\dev-api.ps1
.\scripts\dev-worker.ps1
.\scripts\dev-beat.ps1
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend

```powershell
cd apps\web
npm install
npm run dev
```

Or: `.\scripts\dev-web.ps1` from repo root.

App: [http://localhost:3000](http://localhost:3000)

## Deploy frontend to Vercel

The Next.js app lives in `apps/web`.

### Option A — Deploy button (recommended)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fziauldin%2FLeadGen&project-name=leadsgen-web&root-directory=apps%2Fweb&env=NEXT_PUBLIC_API_URL&envDescription=URL%20of%20your%20deployed%20FastAPI%20backend)

This pre-fills **Root Directory** as `apps/web` (required for monorepos).

### Option B — Manual import

1. Import [github.com/ziauldin/LeadGen](https://github.com/ziauldin/LeadGen) at [vercel.com/new](https://vercel.com/new).
2. **Required:** set **Root Directory** to `apps/web`:
   - Project **Settings** → **Build and Deployment** → **Root Directory** → **Edit** → `apps/web` → **Save**
3. **Reset build overrides** (important if you deployed before fixing the monorepo):
   - **Settings** → **Build and Deployment** → **Framework Settings**
   - Framework Preset: **Next.js**
   - Turn **Override** **off** for Install Command, Build Command, Output Directory, and Development Command
   - Install should default to `npm ci`, build to `npm run build`, output to `.next`
   - Remove any `cd apps/web && …` prefixes — they break once Root Directory is already `apps/web`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` — your deployed FastAPI backend URL (e.g. `https://api.example.com`)
5. **Deployments** → open the latest deployment → confirm status is **Ready** (not Error or Canceled), then open the **Visit** link.

The FastAPI backend is **not** deployed by Vercel. Host it separately (Railway, Render, Fly.io, etc.) and point `NEXT_PUBLIC_API_URL` at that URL. Ensure the API allows your Vercel domain in `CORS_ORIGINS`.

### Vercel troubleshooting

| Symptom | Fix |
|---------|-----|
| `404: NOT_FOUND` (Vercel plain error page, not the app) | No successful deployment on that URL. Check **Deployments** for a green **Ready** build. Set Root Directory to `apps/web`, reset build overrides (step 3 above), redeploy. |
| `No Next.js version detected` | Root Directory is still the repo root. Set it to `apps/web` and redeploy. |
| `npm ci` / no `package-lock.json` | Ensure `apps/web` is committed as normal files (not a git submodule). |
| App loads but API calls fail | Set `NEXT_PUBLIC_API_URL` in Vercel env vars and redeploy. The backend must be running separately. |

### 4. Demo login

After `python scripts/seed.py` (use `python scripts/seed.py --reset` to refresh demo data):

| Field    | Value                 |
|----------|-----------------------|
| Email    | `demo@wellpredict.io` |
| Password | `demo1234`            |

## End-to-end demo workflow (UI)

1. **Sign in** at `/login` with the demo account.
2. **Dashboard** — review lead and campaign stats.
3. **Niches** — view or edit the WellPredict UK niche.
4. **Search** — generate queries, run mock search, save selected results as leads.
5. **Leads** — import/export CSV, recalculate scores, open a lead detail page.
6. **Companies** — run website enrichment on a company.
7. **Email studio** — preview, generate draft, approve (compliance checklist required).
8. **Campaigns** — create a campaign, add outreach-ready leads, start, process sends.
9. **Replies** — sync mock replies, classify, add notes, export CSV.
10. **Settings** — configure sender identity and suppression list.

## Project structure

```
LeadsGen/
├── apps/web/              Next.js 15 frontend
├── services/api/          FastAPI backend
├── scripts/               Dev helper scripts (PowerShell)
├── Agents.md              Project guidelines (root)
├── apps/web/Agents.md     Frontend conventions
├── services/api/Agents.md Backend conventions
└── .env.example           Environment template
```

## Database migrations

Run from `services/api`:

```powershell
alembic upgrade head
```

Migration order:

1. `0bfd962c64c3` — initial schema
2. `a1b2c3d4e5f6` — user settings
3. `b2c3d4e5f6a7` — search results JSON
4. `c3d4e5f6a7b8` — enrichment message
5. `d4e5f6a7b8c9` — reply notes

## API overview

| Area        | Prefix            | Notes                                      |
|-------------|-------------------|--------------------------------------------|
| Auth        | `/auth`           | register, login, me                        |
| Niches      | `/niches`         | CRUD                                       |
| Leads       | `/leads`          | CRUD, CSV import/export, outreach readiness |
| Companies   | `/companies`      | list, enrich                               |
| Search      | `/searches`       | generate queries, run, save results        |
| Scoring     | `/scoring`        | rules, recalculate                         |
| Emails      | `/emails`         | templates, preview, generate, approve      |
| Campaigns   | `/campaigns`      | CRUD, add leads, start/pause, process sends |
| Replies     | `/replies`        | list, sync, export CSV, classify, notes    |
| Dashboard   | `/dashboard`      | summary stats                              |
| Settings    | `/settings`       | sender profile                             |
| Suppressions| `/suppressions`   | list, create, delete                         |
| Compliance  | `/unsubscribe`    | public opt-out endpoint                    |
| Health      | `/health`         | liveness (`ok`)                            |
| Health      | `/health/ready`   | readiness (database + Redis; 503 if degraded) |

## Continuous integration

GitHub Actions workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR:

- Backend: `pytest` in `services/api`
- Frontend: `npm run lint` and `npm run build` in `apps/web`

Run the same checks locally with:

```powershell
.\scripts\test-all.ps1
```

## Development commands

```powershell
# Run all CI checks locally (backend tests + frontend lint/build)
.\scripts\test-all.ps1

# Backend tests only
cd services\api
pytest tests/ -v

# Frontend lint + build
cd apps\web
npm run lint
npm run build
```

## Environment variables

See [`.env.example`](.env.example) for the full list. Key values:

- `DATABASE_URL` — optional; defaults to SQLite at `services/api/data/leadsgen.db`
- `REDIS_URL` — Celery broker
- `SECRET_KEY` — JWT signing (change in production)
- `SECRET_ENCRYPTION_KEY` — Fernet key for encrypting provider API keys (required)
- `CORS_ORIGINS` — frontend origin (`http://localhost:3000`)
- `SEARCH_PROVIDER` — `mock` by default
- `EMAIL_PROVIDER` — `mock` by default
- `API_PUBLIC_URL` — used in unsubscribe links in generated emails

## Compliance

This is a compliant B2B outreach tool, not a spam or LinkedIn automation system.

Hard rules enforced in code:

- No LinkedIn scraping or automation
- No Google SERP scraping (mock/provider abstractions only)
- No send without: approval, source URL, compliance note, suppression pass, not opted out
- Opt-out line in generated emails
- Manual approval before sending

See [Agents.md](Agents.md) for full guidelines.

## MVP complete (Phase 12)

The MVP workflow is fully implemented end-to-end:

| Capability | Status |
|------------|--------|
| Auth, niches, leads (CSV), companies | Done |
| Search (mock + external API providers) | Done |
| Enrichment, scoring, outreach readiness | Done |
| Email studio (preview, generate, approve) | Done |
| Campaigns (throttle, send gate, mock/SMTP) | Done |
| Replies (sync, classify, notes, export) | Done |
| Dashboard, settings, suppressions, opt-out | Done |
| Celery beat (campaign sends + reply sync) | Done |
| Health: `/health` + `/health/ready` | Done |

**Verify your environment** before first run:

```powershell
.\scripts\verify-setup.ps1
```

**Run the full test suite** (mirrors CI):

```powershell
.\scripts\test-all.ps1
```

The API smoke test in `services/api/tests/test_phase12.py` exercises niche → search → lead → score → email → campaign → reply → dashboard in one pass.

Frontend health page: [http://localhost:3000/health](http://localhost:3000/health) — shows liveness and database/Redis readiness.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `unable to open database file` | Run API from `services/api` or set `DATABASE_URL` to an absolute SQLite path |
| `redis-cli ping` fails | Start Redis locally before Celery |
| Frontend cannot reach API | Confirm `NEXT_PUBLIC_API_URL` and API is on port 8000 |
| CORS errors | Add `http://localhost:3000` to `CORS_ORIGINS` |
| Sends not processing | Start Celery worker; campaign must be `active`; emails must be `approved` |
| Empty replies after sync | Process campaign sends first so messages have `sent` status |
