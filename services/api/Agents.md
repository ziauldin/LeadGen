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

## Local development

Native local setup — no Docker required:

* Python venv in `services/api/.venv`
* SQLite database at `services/api/data/leadsgen.db` (auto-created on first run)
* Redis on the host for Celery workers
* Load environment from repo root `.env`

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
