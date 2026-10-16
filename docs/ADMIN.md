# Admin back office

The admin area at `/admin` is for platform operators.

- It's hidden from everyone else: the API answers `404`.
- Admins need two-factor authentication on (`SUPERUSER_REQUIRE_MFA`, default `true`).
- Every action is written to the audit log with an `admin.` prefix.
- Actions on a workspace also appear in that workspace's own audit log.

## Granting access

Superusers are only granted from the command line, never through the API:

```bash
cd services/api
python -m scripts.manage_superusers grant ops@example.com
python -m scripts.manage_superusers list
python -m scripts.manage_superusers revoke ops@example.com
```

On Railway, run it with `railway run python -m scripts.manage_superusers ...`.

## What admins can do

| Area | Capabilities |
|---|---|
| Overview | Users, workspaces by plan, active workspaces, sends and replies. Health of the database, Redis and worker heartbeat, plus queued or failed emails, providers in error, webhook backlog and open data requests. |
| Workspaces | Search by name or member email. See members, leads, 30-day sends, bounce and complaint rates. Change the plan, set limit and feature overrides (JSON), and set per-workspace feature flags. |
| Sending | Suspend sending with a reason, or resume it. While suspended, the send gate defers every email. |
| View as customer | Impersonate a workspace member in a new tab for up to 30 minutes (hard cap: `IMPERSONATION_MAX_MINUTES`). See below for how sessions work. |
| Users | Search users, and disable or enable accounts. Disabling signs the person out everywhere. Admins can't disable themselves. |
| Abuse review | Workspaces with at least 20 sends in 7 days and a bounce rate of 5% or more, or a complaint rate of 0.3% or more. Also sign-ups from the last 14 days from disposable domains, or still unverified after 3 days. |
| Global suppressions | Block an address or domain for every workspace, e.g. spam traps. Platform hard bounces and complaints are added automatically. |
| Admin audit trail | Every `admin.*` action, including superuser grants made from the CLI. |

### Impersonation sessions

- **Reason required:** each session needs a reason, which is recorded in the customer's audit log.
- **Read-only by default:** non-GET requests are refused unless "Allow changes" is ticked.
- **Always locked:** sign-in and security settings, API keys and webhooks, SSO, roles, members and invitations, billing and data requests, even with changes allowed.
- **Separate session:**
  - The token lives only in that tab's `sessionStorage`, is never renewed, and can't open the admin area.
  - The admin's own session is untouched.
  - A banner shows on every page until **End session**.
  - Revoking the admin's superuser access ends any open sessions.

## Feature flags per workspace

The `FEATURE_*` environment variables set the default for the whole server. Admins can override these flags for one workspace, for example to pilot a feature with a few customers:

- `ai_emails`
- `imap`
- `inbound_webhooks`
- `sso`
- `public_api`

Code reads flags through `app.core.flags.feature_enabled(name, workspace)`.
