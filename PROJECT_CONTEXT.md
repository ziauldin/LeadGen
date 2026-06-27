# LeadsGen — Full Project Context

> **Purpose of this file**: Provide complete context to an AI assistant (e.g., ChatGPT) about the LeadsGen codebase so it can help with development, debugging, and feature work without needing the repo files directly.

---

## 1. What This Project Is

**LeadsGen** is a full-stack, compliance-first **B2B lead-intelligence and outreach workflow system**. It helps founders and operators:

1. Define a target **niche** (industry, country, roles, keywords, company size)
2. Generate **search queries** (Google X-ray style) and collect public company/lead URLs via approved search APIs
3. **Enrich** company records (website crawl, public email extraction, robots.txt compliance)
4. **Score** leads with a transparent rule-based system
5. **Generate personalised first-touch emails** (template-based, no LLM required for MVP)
6. Run **controlled outreach campaigns** (throttle limits, suppression, manual approval, opt-out)
7. **Track replies** (sync, classify, note, export CSV)
8. Move qualified leads toward **discovery calls**

**This is NOT a spam tool, LinkedIn automation tool, or Google SERP scraper.**

---

## 2. Monorepo Structure

```
LeadsGen/                        ← Repo root
├── apps/
│   └── web/                     ← Next.js 15 frontend (TypeScript)
├── services/
│   └── api/                     ← Python FastAPI backend
├── scripts/                     ← PowerShell dev-helper scripts
├── .env.example                 ← Environment variable template
├── Agents.md                    ← Root-level project hard rules
├── Phases.md                    ← Original design/phases spec
├── README.md                    ← Developer setup guide
└── vercel.json                  ← Vercel root deployment config
```

---

## 3. Tech Stack

### Frontend — `apps/web/`

| Layer | Technology |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| UI Components | shadcn/ui (Base UI) |
| Server State | TanStack Query v5 |
| Forms | React Hook Form v7 + Zod v4 |
| Charts | Recharts v3 |
| Toasts | Sonner |
| Icons | Lucide React |
| Theme | next-themes |
| React | 19.1.0 |

### Backend — `services/api/`

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115+ |
| Language | Python 3.12+ |
| ORM | SQLAlchemy 2 (async-capable) |
| Migrations | Alembic |
| Database | SQLite (default local) / PostgreSQL (production) |
| Task Queue | Celery 5 + Redis 5 |
| Validation | Pydantic v2 / pydantic-settings |
| HTTP Client | httpx |
| HTML Parsing | BeautifulSoup4 |
| Domain Parsing | tldextract |
| Email Validation | email-validator |
| Auth | JWT (python-jose) + bcrypt passwords |
| Encryption | Fernet (cryptography) — for stored provider API keys |

---

## 4. Frontend Architecture (`apps/web/src/`)

### Directory Layout

```
src/
├── app/                         ← Next.js App Router pages
│   ├── layout.tsx               ← Root layout
│   ├── page.tsx                 ← Root redirect (→ /dashboard)
│   ├── globals.css
│   ├── (auth)/                  ← Unauthenticated route group
│   │   ├── login/               ← /login
│   │   └── register/            ← /register
│   ├── (app)/                   ← Authenticated route group
│   │   ├── layout.tsx           ← Sidebar + topbar shell
│   │   ├── dashboard/           ← /dashboard
│   │   ├── niches/              ← /niches, /niches/[id]
│   │   ├── search/              ← /search
│   │   ├── leads/               ← /leads, /leads/[id]
│   │   ├── companies/           ← /companies
│   │   ├── campaigns/           ← /campaigns, /campaigns/[id]
│   │   ├── email-studio/        ← /email-studio
│   │   ├── replies/             ← /replies
│   │   └── settings/            ← /settings
│   └── health/                  ← /health (public status page)
├── components/
│   ├── layout/                  ← Sidebar, Topbar, PageHeader
│   ├── auth/                    ← LoginForm, RegisterForm
│   ├── niches/                  ← NicheForm, NicheCard
│   ├── leads/                   ← LeadTable, LeadStatusBadge, ScoreBadge
│   ├── companies/               ← CompanyCard, EnrichmentStatus
│   ├── search/                  ← SearchQueryBuilder, SearchResultsTable
│   ├── campaigns/               ← CampaignStepEditor, CampaignCard
│   ├── emails/                  ← EmailPreview, EmailApproval
│   ├── replies/                 ← ReplyClassificationBadge, ReplyTable
│   ├── settings/                ← SenderForm, SuppressionList
│   ├── compliance/              ← ComplianceChecklist
│   ├── shared/                  ← EmptyState, ConfirmDialog, LoadingSpinner
│   └── ui/                      ← shadcn/ui primitives
├── hooks/
│   └── use-auth.tsx             ← Auth context + useAuth hook
├── lib/
│   ├── api/
│   │   ├── client.ts            ← Typed fetch wrapper (reads NEXT_PUBLIC_API_URL)
│   │   ├── endpoints.ts         ← All API call functions (typed, return Promises)
│   │   └── types.ts             ← All shared TypeScript types
│   ├── constants/               ← Route constants, label maps
│   └── validations/             ← Zod schemas for forms
└── providers.tsx                ← QueryClientProvider + ToasterProvider
```

### Key Patterns

- **API client**: `lib/api/client.ts` wraps `fetch` with auth token (from `localStorage`), base URL from `process.env.NEXT_PUBLIC_API_URL`, and JSON error parsing.
- **Data fetching**: All server state goes through **TanStack Query** hooks. Query keys follow `[resource, id?, filters?]` pattern.
- **Auth**: JWT token stored in `localStorage`. `useAuth()` hook handles login, logout, `me` fetch, and redirect to `/login` when unauthenticated.
- **Forms**: React Hook Form + Zod resolver. Validation schemas live in `lib/validations/`.
- **Outreach UX guardrails**: Before showing a "send" action, the UI checks: lead has email, lead is not opted out, lead is not suppressed, source URL exists, compliance note exists, email is manually approved.

---

## 5. Backend Architecture (`services/api/app/`)

### Directory Layout

```
app/
├── main.py                      ← FastAPI app factory, CORS, router mounting
├── core/
│   ├── config.py                ← Settings (pydantic-settings, .env file)
│   ├── database.py              ← SQLAlchemy engine + session factory
│   ├── security.py              ← JWT creation/decode, password hashing, Fernet encryption
│   ├── celery_app.py            ← Celery instance + beat schedule
│   ├── logging.py               ← structlog setup
│   └── exceptions.py            ← Global HTTP/validation exception handlers
├── models/                      ← SQLAlchemy ORM models (one file per entity)
│   ├── enums.py                 ← All Enum classes
│   ├── user.py
│   ├── niche.py
│   ├── lead.py
│   ├── company.py
│   ├── email_contact.py
│   ├── campaign.py              ← Campaign + CampaignStep
│   ├── email_message.py
│   ├── reply.py
│   ├── search_query.py
│   ├── suppression.py
│   ├── audit_log.py
│   ├── provider_credential.py  ← Encrypted API key storage per provider
│   ├── user_settings.py        ← Sender name/company/address per user
│   └── mixins.py               ← Timestamped mixin
├── schemas/                     ← Pydantic v2 request/response schemas
│   ├── auth.py
│   ├── niche.py
│   ├── lead.py
│   ├── company.py
│   ├── campaign.py
│   ├── email.py
│   ├── reply.py
│   ├── search.py
│   ├── scoring.py
│   ├── settings.py
│   ├── suppression.py
│   ├── provider_settings.py
│   └── common.py               ← Paginated[T] generic
├── api/
│   ├── deps.py                  ← FastAPI dependencies (get_db, get_current_user)
│   └── routes/
│       ├── auth.py              ← POST /auth/register, /auth/login, GET /auth/me
│       ├── niches.py            ← CRUD /niches
│       ├── searches.py          ← POST /searches/generate, /searches/{id}/run, /searches/{id}/save
│       ├── leads.py             ← CRUD /leads, CSV import/export, outreach readiness
│       ├── companies.py         ← GET /companies, POST /companies/{id}/enrich
│       ├── scoring.py           ← GET /scoring/rules, POST /scoring/recalculate
│       ├── emails.py            ← GET /emails/templates, POST /emails/preview, /emails/generate, /emails/{id}/approve
│       ├── campaigns.py         ← CRUD /campaigns, add leads, start/pause, process sends
│       ├── replies.py           ← GET /replies, POST /replies/sync, export CSV, classify, notes
│       ├── dashboard.py         ← GET /dashboard/summary
│       ├── settings.py          ← GET/PUT /settings (sender profile) + /suppressions CRUD
│       ├── provider_settings.py ← CRUD /provider-settings (encrypted API keys per provider)
│       ├── compliance.py        ← GET /unsubscribe (public opt-out endpoint)
│       └── health.py            ← GET /health, /health/ready
├── services/                    ← Business logic (never in routes)
│   ├── search/
│   │   ├── base.py              ← Abstract SearchProvider interface
│   │   ├── mock_provider.py     ← Default mock results
│   │   ├── manual_import.py     ← CSV-based manual import
│   │   ├── external_providers.py← Google CSE, Bing, SerpAPI implementations
│   │   ├── query_generator.py   ← Generates X-ray style queries from niche
│   │   ├── search_service.py    ← Orchestrates provider selection + run
│   │   └── provider_factory.py  ← Picks provider from DB credentials or env
│   ├── enrichment/
│   │   ├── enricher.py          ← Main enrichment orchestrator
│   │   ├── website_finder.py    ← Finds company website from domain
│   │   ├── website_crawler.py   ← Fetches homepage + contact/about pages
│   │   ├── email_extractor.py   ← Extracts + classifies public emails from HTML
│   │   └── robots_checker.py    ← Checks robots.txt before crawling
│   ├── scoring/
│   │   ├── rules.py             ← SCORING_RULES list (all rule definitions + points)
│   │   └── lead_score.py        ← Applies rules to a lead, returns score + breakdown
│   ├── email_generation/        ← Template-based email generation (no LLM required)
│   ├── sending/
│   │   ├── base.py              ← Abstract EmailSender interface
│   │   ├── mock_provider.py     ← Dev/test mock sender
│   │   ├── smtp_provider.py     ← SMTP fallback sender
│   │   ├── external_providers.py← Resend, SendGrid, Mailgun implementations
│   │   ├── gate.py              ← Sending pre-flight checks (all hard rules enforced here)
│   │   ├── sender.py            ← Orchestrates gate → provider → audit log
│   │   └── provider_factory.py  ← Picks email provider from DB credentials or env
│   ├── compliance/              ← Suppression checks, opt-out handling, consent notes
│   ├── companies/               ← Company CRUD + enrichment trigger
│   ├── leads/                   ← Lead CRUD, CSV import/export, outreach readiness
│   ├── campaigns/               ← Campaign CRUD, step management, send processing
│   ├── replies/                 ← Reply sync (mock or webhook), classification
│   └── health/                  ← DB + Redis liveness checks
└── workers/
    ├── enrichment_jobs.py       ← Celery task: run_enrichment(company_id)
    ├── search_jobs.py           ← Celery task: run_search(search_query_id)
    ├── campaign_jobs.py         ← Celery task: process_campaign_sends (beat schedule)
    └── reply_jobs.py            ← Celery task: sync_replies (beat schedule)
```

---

## 6. Database Schema (SQLAlchemy / Alembic)

### Entities & Key Fields

**users**
- `id`, `name`, `email`, `hashed_password`, `role` (admin/operator), `created_at`

**user_settings** (1-to-1 with user)
- `sender_name`, `sender_company`, `business_address`

**niches**
- `user_id` (FK), `name`, `country`, `industry`, `target_roles` (JSON), `keywords` (JSON), `exclusion_keywords` (JSON), `company_size_min`, `company_size_max`

**search_queries**
- `niche_id` (FK), `query_text`, `provider` (mock/google_cse/bing/serpapi/manual), `status` (pending/running/completed/failed), `results` (JSON), `result_count`

**companies**
- `name`, `website`, `domain`, `industry`, `country`, `size_estimate`, `contact_page_url`, `about_page_url`, `robots_checked`, `enrichment_status` (pending/in_progress/completed/failed), `enrichment_message`

**leads**
- `niche_id` (FK), `company_id` (FK nullable), `full_name`, `job_title`, `linkedin_url`, `source_url`, `source_provider`, `status` (new/enriched/qualified/ready_for_outreach/contacted/replied/meeting_booked/client/disqualified/opted_out), `score` (int), `qualification_notes`, `compliance_source_note`

**email_contacts**
- `lead_id` (FK), `company_id` (FK), `email`, `email_type` (generic/role_based/personal/named), `confidence` (float), `source_url`, `is_role_based`, `is_personal`, `is_verified`, `opted_out` (bool)

**campaigns**
- `niche_id` (FK), `name`, `status` (draft/active/paused/completed), `daily_send_limit`, `sending_window_start` (time str), `sending_window_end` (time str)

**campaign_steps** (multi-step sequences)
- `campaign_id` (FK), `step_number`, `delay_days`, `subject_template`, `body_template`

**email_messages**
- `campaign_id` (FK), `lead_id` (FK), `recipient_email`, `subject`, `body`, `status` (draft/pending_approval/approved/sent/failed/bounced), `sent_at`, `provider_message_id`, `reply_status`, `bounce_status` (none/hard/soft), `unsubscribe_token`

**replies**
- `email_message_id` (FK), `from_email`, `body`, `classification` (positive/neutral/objection/unsubscribe/bounce/unknown), `received_at`, `notes`

**suppressions**
- `email` (nullable), `domain` (nullable), `reason`, `source`

**audit_logs**
- `actor_id` (FK), `action`, `entity_type`, `entity_id`, `metadata` (JSON)

**provider_credentials**
- `user_id` (FK), `provider_type` (search/email), `provider_name`, `display_name`, `encrypted_credentials` (Fernet-encrypted JSON), `is_active`, `status` (not_configured/configured/error), `last_tested_at`, `last_test_status`, `last_test_message`

### Migrations (Alembic, in order)

1. `0bfd962c64c3` — initial schema (all core tables)
2. `a1b2c3d4e5f6` — user_settings table
3. `b2c3d4e5f6a7` — search_queries.results JSON column
4. `c3d4e5f6a7b8` — companies.enrichment_message column
5. `d4e5f6a7b8c9` — replies.notes column
6. `e5f6a7b8c9d0` — provider_credentials table

---

## 7. API Endpoints Summary

All routes are prefixed with the API base URL (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`).

| Prefix | Methods | Description |
|---|---|---|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | OAuth2 password login → JWT token |
| `/auth/me` | GET | Current user info |
| `/niches` | GET, POST | List / create niches |
| `/niches/{id}` | GET, PUT, DELETE | Niche detail / update / delete |
| `/searches/generate` | POST | Generate queries from niche |
| `/searches/{id}/run` | POST | Execute search via provider |
| `/searches/{id}/save` | POST | Save selected results as leads |
| `/leads` | GET, POST | List (paginated, filterable) / create lead |
| `/leads/import` | POST | CSV import |
| `/leads/export` | GET | CSV export |
| `/leads/{id}` | GET, PUT, DELETE | Lead detail |
| `/leads/{id}/outreach-ready` | GET | Outreach readiness checks |
| `/companies` | GET | List companies |
| `/companies/{id}` | GET | Company detail |
| `/companies/{id}/enrich` | POST | Trigger enrichment (Celery task) |
| `/scoring/rules` | GET | List scoring rule definitions |
| `/scoring/recalculate` | POST | Re-score all leads for a niche |
| `/emails/templates` | GET | List email templates |
| `/emails/preview` | POST | Preview generated email |
| `/emails/generate` | POST | Generate + save draft email message |
| `/emails/{id}/approve` | POST | Manually approve email for sending |
| `/campaigns` | GET, POST | List / create campaigns |
| `/campaigns/{id}` | GET, PUT, DELETE | Campaign detail |
| `/campaigns/{id}/leads` | POST | Add lead(s) to campaign |
| `/campaigns/{id}/start` | POST | Activate campaign |
| `/campaigns/{id}/pause` | POST | Pause campaign |
| `/campaigns/{id}/process-sends` | POST | Manually trigger send processing |
| `/replies` | GET | List replies |
| `/replies/sync` | POST | Sync replies from provider (or mock) |
| `/replies/export` | GET | Export replies to CSV |
| `/replies/{id}/classify` | PUT | Set reply classification |
| `/replies/{id}/notes` | PUT | Add/update reply notes |
| `/dashboard/summary` | GET | Aggregate stats |
| `/settings` | GET, PUT | Sender identity (name/company/address) |
| `/suppressions` | GET, POST, DELETE | Suppression list management |
| `/provider-settings` | GET, POST | List / create provider credentials |
| `/provider-settings/{id}` | GET, PUT, DELETE | Credential detail |
| `/provider-settings/{id}/test` | POST | Test provider connection |
| `/unsubscribe` | GET | Public opt-out endpoint (adds to suppression) |
| `/health` | GET | Liveness check (`{"status":"ok"}`) |
| `/health/ready` | GET | Readiness check (DB + Redis; 503 if degraded) |

---

## 8. Scoring System

Transparent rule-based scoring (no ML). Score is an integer sum of matched rules.

| Rule Key | Points | Condition |
|---|---|---|
| `target_role_match` | +25 | Lead job title matches a niche target role |
| `niche_keyword_match` | +30 | Lead/company text matches a niche keyword |
| `company_website_exists` | +10 | Linked company has a website URL |
| `public_email_found` | +20 | Non-generic public email contact exists |
| `company_size_match` | +15 | Company size within niche min/max range |
| `generic_email_only` | +5 | Only a generic inbox email (info@, contact@) |
| `no_website` | -20 | Linked company has no website |
| `exclusion_keyword` | -30 | Lead/company text matches an exclusion keyword |
| `opted_out` | 0 | Contact opted out → score forced to 0, status = opted_out |

Score breakdown returned to frontend for transparency. Leads with score ≥ threshold are `qualified`. Leads with all sending checks passed become `ready_for_outreach`.

---

## 9. Email Sending Pre-Flight Gate

The `services/sending/gate.py` enforces **all** of these before any send:

1. Lead has a recipient email
2. Email contact is not opted out
3. Email/domain is not on suppression list
4. Lead has a source URL
5. Lead has a compliance/source note
6. Email message is `approved` status (manual approval required)
7. Campaign is `active`
8. Daily send limit not exceeded
9. Per-domain send limit not exceeded
10. Current time is within campaign's sending window

A failed gate check raises an error and **no email is sent**. No one-click mass send.

---

## 10. Provider Abstraction

Both search and email sending use provider interfaces so no vendor is hardcoded.

### Search Providers
- `mock` — returns fake results (default for local dev/testing)
- `google_cse` — Google Custom Search Engine JSON API
- `bing` — Bing Search API
- `serpapi` — SerpAPI
- `manual` — CSV import

### Email Providers
- `mock` — logs to console, no real send (default for local dev/testing)
- `smtp` — SMTP (dev fallback only)
- `resend` — Resend API
- `sendgrid` — SendGrid API
- `mailgun` — Mailgun API

Provider API keys are stored **encrypted** (Fernet) in the `provider_credentials` table, configured per user via the Settings UI. The `SECRET_ENCRYPTION_KEY` env var is required.

---

## 11. Celery Workers & Background Jobs

Celery uses Redis as broker. Four task modules:

| File | Tasks | Triggered By |
|---|---|---|
| `search_jobs.py` | `run_search(search_query_id)` | API route (async) |
| `enrichment_jobs.py` | `run_enrichment(company_id)` | API route (async) |
| `campaign_jobs.py` | `process_campaign_sends()` | Beat schedule (periodic) |
| `reply_jobs.py` | `sync_replies()` | Beat schedule (periodic) |

The API runs and responds normally without Redis/Celery. Workers are optional for API-only development but required for background enrichment and automated sends.

---

## 12. Compliance Hard Rules (Enforced in Code)

The following are hard rules — violations are prevented at the code level, not just policy level:

- **No LinkedIn scraping, crawling, login, or automation** (LinkedIn URLs stored only if user-provided or from approved API)
- **No Google SERP HTML scraping** (provider abstraction only)
- **No email send without**: approved status, source URL, compliance note, suppression pass, not opted out
- **All generated emails include** an opt-out line
- **Unsubscribe endpoint** (`/unsubscribe?token=...`) adds email to suppression automatically
- **Enrichment respects robots.txt** — robots_checker runs before crawling
- **Audit logs** created for every send action

---

## 13. Enrichment Pipeline

When enrichment is triggered for a company:

1. **robots_checker.py** — fetch and parse `robots.txt`, check if `LeadsGenBot` (or `*`) is blocked
2. **website_finder.py** — construct website URL from domain if not already known
3. **website_crawler.py** — fetch homepage, discover contact/about pages (max 3 pages), rate-limited (1 req/sec)
4. **email_extractor.py** — regex-extract email addresses from HTML, classify each as generic/role_based/personal/named, record source URL
5. Save `EmailContact` records per found email
6. Update `Company.enrichment_status` to `completed` or `failed`
7. Update `Lead.status` to `enriched`

User-Agent: `LeadsGenBot/0.1 (B2B enrichment; respects robots.txt)`

---

## 14. Environment Variables

| Variable | Default | Required | Notes |
|---|---|---|---|
| `DATABASE_URL` | SQLite at `services/api/data/leadsgen.db` | No | PostgreSQL for production |
| `REDIS_URL` | `redis://localhost:6379/0` | No (API works without it) | Required for Celery workers |
| `SECRET_KEY` | `change-me-...` | **Yes (prod)** | JWT signing key |
| `SECRET_ENCRYPTION_KEY` | `""` | **Yes** | Fernet key for provider credential encryption |
| `JWT_ALGORITHM` | `HS256` | No | — |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | No | 24 hours |
| `CORS_ORIGINS` | `http://localhost:3000` | No | Comma-separated |
| `CORS_ORIGIN_REGEX` | None | No | Auto-set in production for Railway/Vercel |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | **Yes (frontend)** | Set in `apps/web/.env.local` |
| `SEARCH_PROVIDER` | `mock` | No | Global fallback; per-user in DB preferred |
| `EMAIL_PROVIDER` | `mock` | No | Global fallback; per-user in DB preferred |
| `DEFAULT_DAILY_SEND_LIMIT` | `20` | No | — |
| `DEFAULT_PER_DOMAIN_LIMIT` | `3` | No | — |
| `DEFAULT_SENDING_WINDOW_START` | `09:00` | No | — |
| `DEFAULT_SENDING_WINDOW_END` | `17:00` | No | — |
| `ENRICHMENT_RATE_LIMIT_SECONDS` | `1.0` | No | Seconds between crawl requests |
| `ENRICHMENT_MAX_PAGES` | `3` | No | Max pages crawled per company |
| `API_PUBLIC_URL` | `http://localhost:8000` | No | Used in unsubscribe links |
| `ENVIRONMENT` | `development` | No | Set to `production` on Railway |

---

## 15. Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- Redis 7+ (Windows: Memurai or WSL)

### Backend

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts\seed.py           # loads demo data
uvicorn app.main:app --reload --port 8000
# Optional workers (separate terminals):
celery -A app.core.celery_app worker -l info
celery -A app.core.celery_app beat -l info
```

### Frontend

```powershell
cd apps\web
# Create apps/web/.env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

### Demo Login (after seed)

| Field | Value |
|---|---|
| Email | `demo@wellpredict.io` |
| Password | `demo1234` |

### Verify Setup

```powershell
.\scripts\verify-setup.ps1
```

---

## 16. Testing

### Backend Tests (pytest)

```powershell
cd services\api
pytest tests/ -v
```

Test files:
- `conftest.py` — in-memory SQLite fixtures, test client
- `test_auth.py` — register/login/me
- `test_phase3.py` through `test_phase12.py` — integration tests per build phase
- `test_phase12.py` — full end-to-end smoke test (niche → search → lead → score → email → campaign → reply → dashboard)
- `test_scoring_search_units.py` — scoring unit tests
- `test_sending_gate_units.py` — sending gate unit tests
- `test_csv_import_units.py` — CSV import parsing unit tests
- `test_email_generation_units.py` — email generation unit tests
- `test_enrichment_units.py` — enrichment unit tests
- `test_compliance_units.py` — compliance/suppression unit tests
- `test_seed.py` — seed data validation
- `test_cors_config.py` — CORS config validation
- `test_provider_settings.py` — provider credential management

### Frontend Checks

```powershell
cd apps\web
npm run lint
npm run build
```

### Run All CI Checks Locally

```powershell
.\scripts\test-all.ps1
```

---

## 17. Deployment

### Backend (Railway)

- Root Directory: `services/api`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Pre-deploy: `alembic upgrade head`
- Add PostgreSQL plugin → set `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- Required env vars: `SECRET_KEY`, `SECRET_ENCRYPTION_KEY`, `ENVIRONMENT=production`, `CORS_ORIGINS`, `API_PUBLIC_URL`

### Frontend (Vercel or Railway)

- Root Directory: `apps/web`
- Build: `npm ci && npm run build`
- Start: `npm run start`
- Required env var (set before build): `NEXT_PUBLIC_API_URL` → deployed API URL

---

## 18. Current Status

**MVP is complete (Phase 12)**. All workflow capabilities are implemented end-to-end:

| Capability | Status |
|---|---|
| Auth, niches, leads (CSV), companies | ✅ Done |
| Search (mock + external API providers) | ✅ Done |
| Enrichment, scoring, outreach readiness | ✅ Done |
| Email studio (preview, generate, approve) | ✅ Done |
| Campaigns (throttle, send gate, mock/SMTP) | ✅ Done |
| Replies (sync, classify, notes, export) | ✅ Done |
| Dashboard, settings, suppressions, opt-out | ✅ Done |
| Celery beat (campaign sends + reply sync) | ✅ Done |
| Health endpoints (liveness + readiness) | ✅ Done |
| Provider credentials (encrypted, per-user) | ✅ Done |

---

## 19. Key Design Decisions & Conventions

1. **Business logic is in `services/`, not route handlers.** Routes validate input, call services, return schemas, handle errors.
2. **Provider abstractions everywhere.** No hardcoded search or email vendor. New providers implement the base interface.
3. **Compliance is code, not policy.** The sending gate enforces all checks before any send — no exceptions in the code.
4. **Transparent scoring.** Score breakdown is returned alongside the score so operators can see why a lead scored as it did.
5. **Template-based email generation.** No LLM dependency for MVP. AI integration can be layered on top later.
6. **SQLite locally, PostgreSQL in production.** SQLAlchemy handles both. The `DATABASE_URL` env var switches between them.
7. **Fernet encryption for provider credentials.** API keys stored in DB are always encrypted. `SECRET_ENCRYPTION_KEY` is required.
8. **Manual approval before send.** No one-click mass sends. Emails must be explicitly approved via the Email Studio.
9. **Audit logs on all sends.** Every outbound email creates an `AuditLog` record.
10. **Enrichment is rate-limited and robots.txt-aware.** 1 req/sec default, max 3 pages per company, respects robots.txt.

---

## 20. Things That Are NOT Implemented (Hard Rules)

The following will never be implemented per `Agents.md`:

- ❌ LinkedIn login automation
- ❌ LinkedIn scraping or profile crawling
- ❌ LinkedIn messaging or connection automation
- ❌ Direct Google SERP HTML scraping
- ❌ Email sending without suppression checks
- ❌ Email sending without unsubscribe/opt-out handling
- ❌ Email sending to opted-out contacts
- ❌ Email sending without source URL or compliance note
- ❌ Hardcoded vendor (always use provider abstractions)
