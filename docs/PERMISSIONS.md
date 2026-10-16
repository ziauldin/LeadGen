# Roles, permissions and the audit log

Every workspace action is checked against a **permission**, not a role name. Each role is a set of permissions.

## Permissions

| Permission | Allows |
|---|---|
| `leads.write` | Add, import, edit, enrich and search for leads and companies |
| `leads.delete` | Delete leads (single and bulk) |
| `campaigns.manage` | Create and edit campaigns, sequences, templates and drafts |
| `campaigns.send` | Start and pause campaigns |
| `campaigns.send_now` | Push due emails out immediately |
| `approvals.approve` | Approve or reject emails |
| `replies.manage` | Label replies, add notes, link replies |
| `data.export` | CSV exports and data requests |
| `providers.manage` | Connect sending, inbox, search and AI providers |
| `settings.manage` | Workspace profile, AI settings, suppressions, policies |
| `members.manage` | Invite people, change roles, remove members |
| `sso.manage` | Verified domains and identity providers |
| `api_keys.manage` | API keys and outbound webhooks |
| `audit.view` | Read and export the audit log |
| `billing.manage` | Plan, payment method and invoices |

## Built-in roles

- **Owner:** every permission.
- **Admin:** every permission except `billing.manage`.
- **Member:** `leads.write`, `leads.delete`, `campaigns.manage`, `campaigns.send`, `approvals.approve`, `replies.manage` and `data.export`.

Actions that send email, invite people or add credentials also need a verified email address.

## Custom roles (Enterprise)

Admins create custom roles in **Settings → Roles**, then assign them on the **Members** page.

- A custom role replaces the member permission set for the people who have it. It only applies to people with the member role; owners and admins keep their full sets.
- Nobody can create, edit or assign a role that includes a permission they don't hold. This prevents privilege escalation.
- Changes take effect on the next request. Deleting a role puts its members back on the standard member permissions.

API:

- `GET /workspaces/current/permissions` returns your role, custom role and effective permissions.
- `GET /roles/permissions` returns the permission catalogue.
- `GET /roles` lists built-in and custom roles.
- `POST /roles`, `PATCH /roles/{id}` and `DELETE /roles/{id}` manage custom roles. These need `members.manage` and the `custom_roles` plan feature.
- `PATCH /workspaces/current/members/{user_id}` accepts `{"custom_role_id": 3}`. Send `null` to clear it.

## Audit log

**Settings → Audit log** (`audit.view`) lists who changed what: members, roles, settings, providers, SSO and sign-in events. You can filter by action prefix, person and date range, and export to CSV with `GET /audit-logs/export`. Exported cells are protected against spreadsheet formula injection.

Retention depends on the plan:

| Plan | Retention |
|---|---|
| Free | 30 days |
| Starter | 90 days |
| Pro | 1 year |
| Enterprise | 2 years |

A daily Celery beat task, `ops.purge_audit_logs`, deletes entries older than the plan's window. Entries that don't belong to a workspace are kept for 2 years.
