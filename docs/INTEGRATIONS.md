# CRM integrations (HubSpot, Pipedrive)

Turn them on with `FEATURE_INTEGRATIONS=true`, or per workspace from the admin area. They're included in the Pro and Enterprise plans (plan feature `integrations`). An admin connects a CRM under **Settings → Integrations**. Connecting needs the `providers.manage` permission and a verified email address.

## What syncs

| Setting (on by default) | What happens |
|---|---|
| Send interested leads as contacts | When a lead sends an interested reply, they're created in the CRM, or updated if a contact with that email already exists. |
| Send deals | New and changed deals are pushed: title, value, currency and expected close date. The first push links the deal to its lead's contact, pushing the contact too. Open deals keep the stage they have in the CRM; won and lost are pushed. |
| Bring back won and lost | Every 15 minutes (`integrations.pull_statuses` beat task), deals won or lost in the CRM move to the first Won or Lost stage here. The move is audited, with the CRM as the source. |

**Sync now** pushes, in the background:

- every lead with an interested reply
- every deal

There are up to 500 of each per run. It's safe to run again: links remember which remote record each lead and deal maps to (`integration_links`), so nothing is duplicated.

### When syncs run

- **How pushes are triggered:** a push is queued in the transaction that changed the lead or deal. It runs as a Celery task (`integrations.sync_object`) only after that transaction commits, so a slow CRM never slows the app.
- **The sync log:** every push and pull is recorded with its result (`integration_sync_logs`). Open it from **Sync log** on the integration.
- **Lost access:** if the CRM refuses access (revoked app or token), the connection is marked as needing a reconnect and stops syncing. Reconnecting updates the stored credentials and keeps the links.
- **Disconnecting:** deletes the connection, its links and its log. Records already in the CRM stay there.

## HubSpot

- **How it connects:** OAuth with a public HubSpot app.
- **Scopes:** `oauth`, `crm.objects.contacts.read/write` and `crm.objects.deals.read/write`.
- **Tokens:** access and refresh tokens are stored encrypted, and refreshed automatically.
- **Where deals go:** HubSpot's default pipeline. They start in "Appointment scheduled", and won or lost map to `closedwon` or `closedlost`.

**Operator setup:**

1. Create an app in a HubSpot developer account.
2. Set its redirect URL to `https://<FRONTEND_URL>/api/integrations/oauth/hubspot/callback`.
3. Add the scopes above.
4. Set `HUBSPOT_CLIENT_ID` and `HUBSPOT_CLIENT_SECRET`.

Until HubSpot lists the app, only test accounts can install it.

## Pipedrive

Each workspace pastes:

- **an API token**, from Pipedrive's Personal preferences → API
- **its company domain**: `acme` for `acme.pipedrive.com`

The token is checked against `/users/me` before it's saved, then stored encrypted. Requests only go to `<domain>.pipedrive.com`, and the domain must be a single plain label, so a workspace can't point the server at another host.

Contacts become persons with a work email. Deals keep their status (open, won or lost).

## API

| Method | Path |
|---|---|
| GET | `/integrations` (providers, connections, whether the flag and plan allow them) |
| POST | `/integrations/hubspot/connect` (returns the HubSpot consent URL) |
| POST | `/integrations/pipedrive` (`{"api_token", "company_domain"}`) |
| PATCH, DELETE | `/integrations/{id}` |
| POST | `/integrations/{id}/sync` |
| GET | `/integrations/{id}/logs` |

## Follow-ups

- **Salesforce:** not built yet. It would plug into the same `CrmClient` interface (`app/services/integrations/clients.py`): OAuth web-server flow with a connected app, Contact and Opportunity upserts by email, and Opportunity `IsWon`/`IsClosed` for status. It also needs per-org instance URLs and API-version pinning.
- **Field mapping and choosing a pipeline:** today contacts use standard fields and deals use the default pipeline.
