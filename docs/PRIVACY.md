# Privacy and data governance

Each workspace is the **controller** of the lead data it holds. LeadsGen is the **processor**. These features help a workspace meet its GDPR and UK GDPR duties.

## Lawful basis per lead

Every lead records a lawful basis, `lawful_basis`, which is one of:

- `legitimate_interest` (the default)
- `consent`
- `contract`

Leads can also carry a legitimate-interest note, `lawful_basis_note`, explaining why the email is reasonable and expected for that person. Both fields are on the lead page and in the API (`POST/PATCH /leads`).

`validate_lead_for_outreach` blocks approval and sending when a lead has no valid basis. Under **Settings → Privacy**, a workspace can also require the legitimate-interest note before outreach.

Existing leads were backfilled to `legitimate_interest`. Their existing source note still serves as the record of where the data came from.

## Data subject requests

**Settings → Privacy → Data requests.** You need the `privacy.manage` permission, which owners and admins have by default.

- **Export a person's data:** builds a zip containing `README.txt` and `person.json`. It covers every contact, lead, company, email, reply, enrollment, delivery event and suppression for that email address.
- **Erase a person:** permanently deletes their contacts, leads, emails, replies, enrollments and delivery events.
  - Readable suppressions for the address are replaced by a single SHA-256 hash, so the person stays blocked from all campaigns without the workspace keeping their address.
  - Earlier export files for the same person are deleted.
  - The request and audit log keep only the hash.
- **Export workspace:** one CSV per table: niches, companies, leads, contacts, campaigns, steps, enrollments, templates, emails, replies and suppressions. Provider credentials are never included. This needs `data.export`, so members can use it, and each member sees only their own exports.

Requests run as a Celery job (`privacy.process_request`). Files are stored with the storage backend (local disk or S3/R2) and downloaded through 15-minute signed links. Files are deleted after 7 days.

API:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/privacy/requests` | Start a request: `{"kind": "export"\|"erase"\|"workspace_export", "email": "…", "note": "…"}` |
| `GET` | `/privacy/requests` | List requests |
| `POST` | `/privacy/requests/{id}/download` | Get a signed download link |
| `POST` | `/privacy/requests/{id}/retry` | Retry a failed request |
| `GET`, `PUT` | `/privacy/settings` | Read or change retention and the legitimate-interest note policy |

## Retention

The daily beat task `privacy.apply_retention` applies each workspace's rules:

- **Delete leads never emailed after** 6 months to 3 years, or off. Leads with any sent, bounced or complained email are kept.
- **Delete replies older than** 6 months to 3 years, or off.
- Raw provider webhook payloads are always deleted after 30 days once processed.
- Expired export files are removed.

Each deletion is written to the audit log with counts only.

## Subprocessors

The public page `/subprocessors` lists them, and `docs/SUBPROCESSORS.md` has the same content. Update both, and `apps/web/src/lib/subprocessors.ts`, before adding a platform subprocessor.
