# /AGENTS.md

## Project

This repository contains a full-stack B2B lead-intelligence and outreach workflow system.

The app helps users:

* choose a niche,
* generate compliant search queries,
* collect lead/company URLs through approved providers,
* enrich public company website data,
* extract public business contact information,
* score leads,
* generate personalised emails,
* send controlled outreach campaigns,
* track replies,
* move qualified leads toward discovery calls.

This is not a spam tool and not a LinkedIn automation tool.

## Hard rules

Do not implement:

* automated LinkedIn login,
* LinkedIn scraping,
* LinkedIn profile crawling,
* LinkedIn messaging automation,
* LinkedIn connection automation,
* direct scraping of Google search result HTML,
* email sending without suppression checks,
* email sending without unsubscribe/opt-out handling,
* email sending to opted-out contacts,
* email sending without a source URL or compliance/source note.

Use provider abstractions instead of hardcoding one vendor.

## Tech stack

Frontend:

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui
* TanStack Query
* React Hook Form
* Zod

Backend:

* Python
* FastAPI
* SQLite (default) or PostgreSQL
* SQLAlchemy 2
* Alembic
* Redis
* Celery
* Pydantic

Local development:

* Native local setup (Python venv, npm, SQLite, and Redis for Celery)
* No Docker required

## Product tone

The product should feel like a professional B2B SaaS tool:

* clear,
* calm,
* practical,
* compliance-aware,
* founder/operator friendly,
* not flashy,
* not spammy.

## Default outreach tone

Generated emails should be:

* short,
* plain English,
* low-pressure,
* founder-led,
* role-relevant,
* non-hype,
* no emojis,
* no false familiarity,
* no exaggerated claims,
* with a soft question at the end,
* with an opt-out line.

## Compliance model

Every lead/contact should have:

* source URL,
* source provider,
* compliance/source note,
* opt-out status,
* suppression check,
* audit trail.

Every email campaign should have:

* manual approval before send,
* daily send limit,
* per-domain throttle,
* unsubscribe token,
* suppression check,
* sending window,
* status tracking.

## Data privacy

Store only business-relevant contact data needed for B2B outreach.

Do not store sensitive personal data.

Do not infer sensitive personal attributes.

Do not generate manipulative or deceptive emails.

Do not hide unsubscribe/opt-out functionality.

## Engineering standards

* Keep code typed.
* Keep services modular.
* Use clear names.
* Avoid unnecessary complexity.
* Prefer explicit service interfaces.
* Avoid production-breaking placeholders.
* Include basic validation and error handling.
* Use environment variables for secrets.
* Do not commit API keys.
* Keep README current.

# /apps/web/AGENTS.md

## Frontend app

This is the Next.js frontend for the lead-intelligence and outreach workflow system.

## Requirements

Use:

* Next.js App Router
* TypeScript
* Tailwind CSS
* shadcn/ui
* TanStack Query
* React Hook Form
* Zod

## UI style

The interface should be:

* clean,
* modern,
* professional,
* light theme by default,
* responsive,
* data-table friendly,
* easy for a founder/operator to use.

Avoid:

* gimmicky animations,
* cluttered dashboards,
* dark-pattern conversion UI,
* fake urgency,
* spam-focused wording.

## Main pages

Create these routes:

* /login
* /register
* /dashboard
* /niches
* /niches/[id]
* /search
* /leads
* /leads/[id]
* /companies
* /campaigns
* /campaigns/[id]
* /email-studio
* /replies
* /settings

## Main layout

Use:

* left sidebar navigation,
* top bar,
* responsive content area,
* reusable page header,
* reusable loading/error states.

## Components

Create reusable components for:

* LeadTable
* LeadStatusBadge
* ScoreBadge
* CompanyCard
* NicheForm
* SearchQueryBuilder
* SearchResultsTable
* EmailPreview
* CampaignStepEditor
* ReplyClassificationBadge
* EmptyState
* ConfirmDialog

## API access

Use a typed API client.

Keep API calls in:

* /lib/api
* /hooks

Use TanStack Query for server state.

Do not hardcode backend URLs. Use environment variables.

## Forms

Use React Hook Form and Zod validation.

Validate:

* niche creation,
* lead creation,
* campaign creation,
* email approval,
* settings forms.

## Outreach UX rules

Before showing a “send” action:

* confirm lead has an email,
* confirm lead is not opted out,
* confirm lead is not suppressed,
* confirm source URL exists,
* confirm compliance/source note exists,
* confirm email has been manually approved.

Do not create one-click mass sending without review.

# /services/api/AGENTS.md

## Backend app

This is the Python FastAPI backend for the lead-intelligence and outreach workflow system.

## Requirements

Use:

* Python 3.12+
* FastAPI
* Pydantic
* SQLite (default) or PostgreSQL
* SQLAlchemy 2
* Alembic
* Redis
* Celery
* httpx
* BeautifulSoup or selectolax
* tldextract
* email-validator

## Architecture

Keep code modular:

app/
core/
models/
schemas/
api/routes/
services/
workers/

Business logic belongs in services, not route handlers.

Route handlers should:

* validate input,
* call services,
* return schemas,
* handle errors cleanly.

## Provider abstractions

Search providers must implement a common interface.

Email sending providers must implement a common interface.

Initial implementation should include:

* mock search provider,
* manual import provider,
* mock email sender,
* optional SMTP sender for development only.

Do not implement direct Google SERP scraping.

Do not implement LinkedIn scraping.

## Enrichment rules

Website enrichment may:

* fetch public company homepages,
* find contact/about/team pages,
* extract public business emails,
* classify emails,
* save source URL for every email,
* use rate limits,
* fail safely.

Website enrichment must not:

* bypass robots.txt,
* evade blocking,
* crawl aggressively,
* collect sensitive personal data,
* scrape LinkedIn.

## Scoring rules

Use transparent rule-based scoring.

Default scoring:

* target role match: +25
* correct niche keyword: +30
* company website exists: +10
* public email found: +20
* company size match: +15
* generic email only: +5
* no website: -20
* exclusion keyword found: -30
* opted out: score 0 and status opted_out

Return score breakdown to the frontend.

## Email generation

Start with template-based generation.

Do not require an LLM provider for MVP.

Generated emails must:

* be short,
* include relevant variables,
* include opt-out line,
* avoid spam wording,
* avoid exaggerated claims,
* avoid false familiarity.

## Sending rules

Before sending, enforce:

* lead has email,
* email contact is not opted out,
* email/domain not suppressed,
* source URL exists,
* compliance/source note exists,
* message manually approved,
* campaign is active,
* daily send limit not exceeded,
* per-domain limit not exceeded,
* sending window is valid.

Sending should create audit logs.

## Suppression

Suppression list must support:

* email-level suppression,
* domain-level suppression,
* reason,
* source.

Unsubscribe endpoint must add suppression automatically.

## Security

Use environment variables for secrets.

Do not log secrets.

Do not return internal errors directly to clients.

Hash passwords.

Use JWT or secure session auth.

Add CORS config for local frontend.

## Migrations

Use Alembic for all schema changes.

Do not modify database schema without a migration.

## Testing

Add basic tests for:

* scoring,
* suppression checks,
* email generation,
* CSV import parsing,
* provider interfaces.
