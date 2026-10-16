# Public API and webhooks

Turn the API on with `FEATURE_PUBLIC_API=true`. Workspaces need a plan with `api_access`, which is Starter and above. Keys and webhook endpoints are managed in **Settings → API & webhooks**, which needs the `api_keys.manage` permission.

## Authentication

```http
GET /v1/me
Authorization: Bearer lg_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

- Keys are shown once. Only a SHA-256 hash is stored, along with a 16-character prefix so you can recognise a key.
- A key acts as the member who created it, limited to its **scopes**. It stops working if that member leaves the workspace, loses the matching permission, the key is revoked or expires, or the plan loses API access.
- Each key is rate limited separately (`RATE_LIMIT_API`, default `120/minute`). Over the limit, requests get `429`.

| Scope | Allows | Creator must have |
|---|---|---|
| `leads:read` | List and read leads and companies | |
| `leads:write` | Create and update leads | `leads.write` |
| `campaigns:read` | List campaigns and enrollments | |
| `campaigns:write` | Enroll leads in campaigns | `campaigns.manage` |
| `replies:read` | List replies | |
| `suppressions:read` | List the do-not-contact list | |
| `suppressions:write` | Add and remove do-not-contact entries | `settings.manage` |

## Endpoints

The OpenAPI document is at `GET /v1/openapi.json`. Lists take `skip` and `limit` (max 200) and return `{items, total, skip, limit}`.

| Method | Path | Scope |
|---|---|---|
| GET | `/v1/me` | any |
| GET | `/v1/leads` (`status`, `niche_id`, `company_id`, `has_email`, `search`) | `leads:read` |
| GET | `/v1/leads/{id}` | `leads:read` |
| POST | `/v1/leads` | `leads:write` |
| PATCH | `/v1/leads/{id}` | `leads:write` |
| GET | `/v1/companies`, `/v1/companies/{id}` | `leads:read` |
| GET | `/v1/campaigns`, `/v1/campaigns/{id}`, `/v1/campaigns/{id}/enrollments` | `campaigns:read` |
| POST | `/v1/campaigns/{id}/enrollments` (`{"lead_ids": [...]}`) | `campaigns:write` |
| GET | `/v1/replies` (`classification`, `campaign_id`) | `replies:read` |
| GET, POST | `/v1/suppressions` | `suppressions:read` / `suppressions:write` |
| DELETE | `/v1/suppressions/{id}` | `suppressions:write` |

`POST /v1/leads` takes the same fields as the app, plus `emails` (up to 10 addresses):

```json
{
  "niche_id": 3,
  "full_name": "Dr Jo Smith",
  "job_title": "Principal Dentist",
  "source_url": "https://example.com/dentists",
  "compliance_source_note": "Public practice listing",
  "lawful_basis": "legitimate_interest",
  "emails": ["jo.smith@smile-dental.co.uk"]
}
```

Enrolling leads creates drafts that still go through approval. Nothing is sent without a person approving it, unless the campaign is set up for that in the app.

### Idempotency

Send `Idempotency-Key: <unique string>` with any `POST`:

- Repeating the request with the same key and body returns the stored response, with the header `Idempotent-Replayed: true`.
- Reusing the key with a different body returns `422`.
- Keys are scoped to the API key.

## Webhooks

Add an endpoint URL and choose events. URLs must be `https` and public. Every delivery goes through the SSRF-safe client, so private and internal addresses are refused.

| Event | `data` |
|---|---|
| `lead.created` | `{"lead": {id, full_name, job_title, niche_id, company_id, status, source_provider, source_url, lawful_basis, emails}}` |
| `email.sent` | `{"email": {id, lead_id, campaign_id, step_number, recipient_email, subject, status, sent_at}}` |
| `email.bounced` | `{"email": {...}, "kind": "hard_bounce" \| "complaint"}` |
| `reply.received` | `{"reply": {id, lead_id, email_message_id, from_email, subject, classification, is_auto_reply, snippet, received_at}}` |
| `enrollment.completed` | `{"enrollment": {id, campaign_id, lead_id, status, current_step}}` |
| `ping` | Sent by **Test** |

Each request body looks like this:

```json
{"id": "evt_…", "type": "reply.received", "created_at": "2026-10-19T09:00:00+00:00", "workspace_id": 1, "data": {…}}
```

The request carries these headers:

- `LeadsGen-Event`
- `LeadsGen-Event-Id`
- `LeadsGen-Delivery`
- `LeadsGen-Signature: t=<unix seconds>,v1=<hex>`

The signature is the HMAC-SHA256 of `"<t>.<raw body>"`, keyed with the endpoint's signing secret (`whsec_…`). Verify it like this:

```python
import hashlib, hmac, time

def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    parts = dict(item.split("=", 1) for item in header.split(","))
    if abs(time.time() - int(parts["t"])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Delivery behaviour:

- **Success:** any `2xx` response within 10 seconds (`OUTBOUND_WEBHOOK_TIMEOUT_SECONDS`).
- **Retries:** after 1 minute, 5 minutes, 30 minutes, 2 hours, 6 hours, 12 hours and 24 hours (8 attempts). After that the delivery is marked `failed`. The `outbound_webhooks.retry_due` beat task runs every minute.
- **Auto-disable:** an endpoint is disabled after 50 failed deliveries in a row. Turning it back on resets the count.
- **Replays:** replaying a delivery from the log sends the same event id, so receivers should de-duplicate on `LeadsGen-Event-Id`.
- **Timing:** events are only sent after the change that caused them is committed.
