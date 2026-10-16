# Deploying to Railway

LeadsGen runs as six Railway services from one repository:

| Service | Root directory | Config file | Notes |
|---|---|---|---|
| **api** | `services/api` | `/services/api/railway.toml` | Runs `alembic upgrade head` before each deploy. Health check: `/health` |
| **worker** | `services/api` | `/services/api/railway.worker.toml` | Celery worker for all queues. Scale replicas for throughput |
| **beat** | `services/api` | `/services/api/railway.beat.toml` | Celery scheduler. **Exactly one replica** |
| **web** | `apps/web` | `/apps/web/railway.toml` | Next.js. Proxies `/api/*` to the API. Health check: `/healthz` |
| **Postgres** | Railway plugin | | Turn on backups |
| **Redis** | Railway plugin | | Celery broker, rate limits, worker heartbeat |

## 1. Create the services

1. Create a project and add the **PostgreSQL** and **Redis** plugins.
2. Add the four services from the repository. For each one, set **Settings → Source → Root Directory** and **Config file path** as in the table above.
3. Give **api** and **web** public domains. Keep worker and beat private.

## 2. Environment variables

Railway's shared variables are the easiest way to give api, worker and beat the same values. Everything is described in [`.env.example`](../.env.example).

**api, worker and beat:**

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `SECRET_KEY` | 48+ random characters |
| `SECRET_ENCRYPTION_KEY` | a Fernet key (see `.env.example`); keep it safe, as it decrypts stored credentials |
| `FRONTEND_URL` | `https://app.example.com` (the web service's public URL) |
| `API_PUBLIC_URL` | `https://api.example.com` (used in unsubscribe links) |
| `CORS_ORIGINS` | `https://app.example.com` |
| `PLATFORM_EMAIL_PROVIDER` | `resend` or `smtp`, plus its key/credentials and `PLATFORM_EMAIL_FROM` |
| `INBOUND_EMAIL_DOMAIN` | optional; see [PROVIDERS.md](PROVIDERS.md#reply-addresses) |
| `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | file storage for exports (Cloudflare R2 or S3). Local disk is lost on redeploy |
| `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `METRICS_TOKEN` | optional observability; see [RUNBOOKS.md](RUNBOOKS.md) |
| `FEATURE_*`, `PLATFORM_LLM_*` | as needed (see the flag table in the README) |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICES`, `BILLING_TRIAL_DAYS`, `BILLING_GRACE_DAYS`, `PLAN_DISPLAY_PRICES` | with `FEATURE_BILLING=true`; the Stripe webhook goes to `https://api.example.com/billing/webhooks/stripe` ([BILLING.md](BILLING.md)) |
| `GOOGLE_OAUTH_*`, `MICROSOFT_OAUTH_*` | social sign-in and mailbox connections ([SSO.md](SSO.md), [PROVIDERS.md](PROVIDERS.md)) |
| `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET` | HubSpot sync ([INTEGRATIONS.md](INTEGRATIONS.md)) |
| `TURNSTILE_SECRET_KEY` | CAPTCHA on sign-up, password reset and repeated failed logins |
| `SUPPORT_EMAIL` | where contact-form and feedback messages go |
| `SUPERUSER_REQUIRE_MFA`, `IMPERSONATION_MAX_MINUTES` | back-office safety; keep the defaults in production ([ADMIN.md](ADMIN.md)) |

The API refuses to start in production when one of these is unsafe:
- `SECRET_KEY` is weak or still the placeholder
- `SECRET_ENCRYPTION_KEY` is missing
- the database isn't PostgreSQL
- a URL isn't https
- CORS uses a wildcard
- the platform mailer is still `console`
- eager Celery is on
- the platform LLM is `mock`

The error message lists what to fix.

**web:**

| Variable | Value |
|---|---|
| `API_INTERNAL_URL` | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}` |
| `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` | optional browser error reporting and source maps |
| `NEXT_PUBLIC_SITE_URL` | the public site's canonical URL (sitemap, Open Graph) |
| `NEXT_PUBLIC_LEGAL_ENTITY`, `NEXT_PUBLIC_LEGAL_ADDRESS`, `NEXT_PUBLIC_CONTACT_EMAIL`, `NEXT_PUBLIC_PRIVACY_EMAIL`, `NEXT_PUBLIC_STATUS_URL` | shown on the legal, contact and footer pages ([MARKETING.md](MARKETING.md)) |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | the CAPTCHA site key, paired with `TURNSTILE_SECRET_KEY` |
| `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST` | optional product analytics, loaded only after cookie consent |

`NEXT_PUBLIC_*` values are compiled into the build, so set them before building the web service.

The browser only talks to the web service. `/api/*` is proxied to the API over Railway's private network, so the refresh-token cookie is first-party and httpOnly.

## 2b. Use a non-superuser database role (row-level security)

PostgreSQL enforces workspace isolation with row-level security, as a second line of defence behind the application's own filters. **Superusers bypass row-level security.** Railway's default `postgres` user is a superuser, so the app should connect as its own role instead.

Run this once in the Railway Postgres console, choosing your own password:

```sql
CREATE ROLE leadsgen_app LOGIN PASSWORD 'change-me' NOSUPERUSER;
CREATE DATABASE leadsgen OWNER leadsgen_app;
```

Then set `DATABASE_URL=postgresql://leadsgen_app:<password>@<host>:<port>/leadsgen` on api, worker and beat.

For an existing database, transfer ownership instead: `ALTER DATABASE … OWNER TO leadsgen_app;` and `REASSIGN OWNED BY postgres TO leadsgen_app;`. Run that as the superuser.

Migrations turn the bypass on for their own connection, so they still work across every workspace.

## 3. Deploy order and migrations

Every API deploy runs `alembic upgrade head` first. Most migrations are additive and safe while old workers are still running.

For a release that contains a **contract migration** (one that drops or renames columns or tables):

1. Scale **worker** and **beat** to 0.
2. Deploy **api** (migrations run), then **web**.
3. Scale **worker** back up, then **beat** to exactly 1.

Before running a migration that moves data on a production database, rehearse it on a copy. For example, `pg_dump` the database, restore it locally, and run `alembic upgrade head` against it.

## 4. Health checks

- `GET /health`: liveness (the process is up). Railway uses this.
- `GET /health/ready`: readiness. It checks the database, Redis, that migrations are at head, and the worker heartbeat. Beat schedules a heartbeat every minute and a worker records it.
  - `ready` (200): everything is working.
  - `degraded` (200): the API works but no worker heartbeat in 3 minutes, so emails won't send.
  - `not_ready` (503): the database, Redis or migrations are broken.
- The web app's **System status** page (`/health`) shows the same information.

## 5. First run

1. Open the web app and create an account. Verify it with the email the platform mailer sends.
2. In **Settings → Providers**, add a sending account (Resend, SendGrid, Mailgun or SMTP), test it and activate it.
3. Copy the webhook URL shown for it into the provider's dashboard ([PROVIDERS.md](PROVIDERS.md)).
4. Run **Settings → Deliverability** and fix any SPF, DKIM or DMARC warnings before sending.

Don't run `scripts/seed.py` in production; it refuses to.

## 6. Backups and recovery

- Turn on Postgres backups in Railway and test a restore at least once.
- `SECRET_ENCRYPTION_KEY` is needed to read stored provider credentials. Keep a copy in your password manager.
- To rotate encryption keys:
  1. Set `SECRET_ENCRYPTION_KEYS=new,old`. New writes use the new key and old values still decrypt.
  2. Re-save the credentials.
  3. Remove the old key.

## Staging and preview environments

- **Staging:** create a second Railway environment (Project, then Environments, then New) from the same repository, tracking `main`. Give it its own Postgres, Redis and secrets, and use test provider accounts there, never production keys. Every merge deploys to staging first. Promote to production by deploying the same commit there.
- **Per-PR previews:** enable Railway PR environments for the project. Each pull request gets its own api, worker, beat and web services with a fresh database. Set `PLATFORM_EMAIL_PROVIDER=smtp` pointing at a Mailpit service and the mock providers, so previews can't send real email.
- **Database migrations** run automatically in every environment through the API's pre-deploy step.

## Staging checklist

Run through this after a release, before announcing it:

- [ ] `/health/ready` reports `ready`, with a fresh worker heartbeat.
- [ ] Sign-up, verification email, password reset, lockout after repeated failures and invitations all work.
- [ ] Send through a real provider test domain:
  - [ ] Gmail shows the unsubscribe button.
  - [ ] A reply is matched and stops the sequence.
  - [ ] A test bounce suppresses the address.
- [ ] A send outside the window is deferred, not failed. A follow-up draft appears after its delay. The campaign completes.
- [ ] If enabled: IMAP polling, AI drafts with a real key, and errors reaching Sentry with request IDs.
