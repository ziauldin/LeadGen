# Runbooks

What to do when something goes wrong in production.

Use these signals to spot a problem:
- `/health/ready`
- the Prometheus metrics below
- Sentry
- logs: JSON, carrying `request_id`, `user_id` and `workspace_id`

## Signals

| Signal | Where | Alert when |
|---|---|---|
| Readiness | `GET /health/ready` (uptime monitor) | Status isn't `ready` for more than 5 minutes |
| Worker heartbeat | `leadsgen_worker_heartbeat_age_seconds` | Over 300 |
| Send queue | `leadsgen_email_messages{status="queued"}` | Over 0 for more than 15 minutes |
| Stuck sends | `leadsgen_email_messages{status="sending"}` | Over 0 for more than 15 minutes (the reaper clears it after 10) |
| Webhook backlog | `leadsgen_webhook_events_pending` | Over 100 |
| Send failures | `rate(leadsgen_email_send_failures_total[15m])` | Unusual spikes per provider |
| Bounces and complaints | `leadsgen_delivery_events_total{kind=~"bounce_hard\|complaint"}` | Spikes. Campaigns auto-pause at 5% bounce or 0.1% complaint |
| API latency | `leadsgen_http_request_duration_seconds` | p95 over 1s on core routes |
| Errors | Sentry | New issue, or a spike in an existing one |

To scrape metrics, set `METRICS_TOKEN` and point Prometheus or Grafana Agent at `GET /metrics` with `Authorization: Bearer <token>`. When running several uvicorn workers, set `PROMETHEUS_MULTIPROC_DIR` to an empty, writable directory.

For traces, set `OTEL_EXPORTER_OTLP_ENDPOINT` (and `OTEL_SAMPLE_RATIO`). FastAPI, Celery and outgoing httpx calls are traced. SQLAlchemy spans start working once the OpenTelemetry instrumentation supports SQLAlchemy 2.1.

For a public status page, point an uptime monitor (Better Stack, UptimeRobot or similar) at `https://<api>/health/ready` and `https://<web>/healthz` and publish its status page.

## Emails aren't sending

1. Check `/health/ready`:
   - **`degraded`:** the worker heartbeat is stale. Check the **worker** and **beat** services on Railway, restart them, and confirm beat has exactly one replica.
   - **`not_ready`:** the database, Redis or migrations are failing. Fix that first.
2. If drafts are sitting in **approved**, check what the campaign is waiting on:
   - the campaign is paused, including auto-pause; the reason is shown on the campaign page
   - the time is outside its sending window or days
   - the daily or per-domain limit is reached
   - a warm-up cap is reached
   - the monthly send quota is used up (402 errors)

   All of these defer messages rather than fail them, so they send on their own once the cause clears.
3. Messages stuck in **sending** are moved to **failed** by the reaper after 10 minutes (stuck **queued** ones go back to **approved** after 15) so a person can review them; they are never resent automatically. Check the provider's dashboard before retrying a failed message.

## Bounce or complaint spike

1. Campaigns pause themselves above the thresholds. Read `auto_paused_reason` on the campaign.
2. Look at the bounced addresses (campaign → Emails, filtered to bounced) and where the leads came from.
3. Run **Settings → Deliverability** for the sending domain.
4. Only resume once the list has been cleaned or verified. Complaints are suppressed across the whole platform.

## Email provider outage

- Temporary errors (HTTP 429/5xx, timeouts) retry with backoff up to 5 times, then fail.
- During a long outage, pause the affected campaigns so attempts aren't used up. Resume afterwards; deferred messages carry on.
- Webhooks queue up at the provider and are retried. Events are stored once even when delivered twice, so replays are safe. Failed events are retried by beat every 10 minutes.

## Database restore

1. Restore the latest Railway Postgres backup into a **new** database and check it, for example with `alembic current` and row counts.
2. Scale worker and beat to 0.
3. Point `DATABASE_URL` at the restored database on api, worker and beat. Deploy the API; migrations run to head.
4. Scale worker and beat back up, with exactly one beat.
5. Messages that were `sending` at the moment of the snapshot go to `failed` through the reaper. Check them against the provider's logs before retrying.

## Rotating secrets

- **`SECRET_KEY`** (signs access tokens): changing it signs everyone out of their current access tokens. Refresh tokens are stored hashed, so sessions recover on the next refresh.
- **`SECRET_ENCRYPTION_KEY`** (stored provider credentials):
  1. Set `SECRET_ENCRYPTION_KEYS=new,old` and deploy.
  2. Have workspaces re-save their credentials, or run a re-encrypt script.
  3. Then remove the old key.
- **Provider keys and webhook secrets:** rotate them in the provider's dashboard, then update them in Settings → Providers.

## Suspected account compromise

1. Use **Sign out on all devices** for the user. This revokes every refresh token and raises `token_version`.
2. Reset their password.
3. Check the audit log for actions taken during the window.
4. If outreach was sent, check the campaign's emails and pause it.
