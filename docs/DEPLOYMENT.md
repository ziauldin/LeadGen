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
| `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `METRICS_TOKEN` | optional observability; see [RUNBOOKS.md](RUNBOOKS.md) |
| `FEATURE_*`, `PLATFORM_LLM_*` | as needed |

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

The browser only talks to the web service. `/api/*` is proxied to the API over Railway's private network, so the refresh-token cookie is first-party and httpOnly.

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
