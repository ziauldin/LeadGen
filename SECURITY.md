# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through [GitHub security advisories](https://github.com/ziauldin/LeadGen/security/advisories/new). Don't open a public issue.

We aim to acknowledge reports within 2 business days and to give you a fix timeline within 7 days. Please give us a reasonable time to fix the issue before disclosing it. We're happy to credit you.

Out of scope:
- denial of service through volume
- reports from automated scanners with no demonstrated impact
- missing best-practice headers that have no exploit
- social engineering

## How LeadsGen protects data

| Area | Control |
|---|---|
| **Tenant isolation** | Every tenant row has `workspace_id`. Application queries are filtered by workspace, and PostgreSQL row-level security enforces the same rule in the database. |
| **Authentication** | Short-lived access tokens (15 min). Refresh tokens are httpOnly, SameSite cookies, rotated on every use; reusing one revokes the whole session family. |
| **Accounts** | Lockout after repeated failures. Email verification before sending outreach, approving emails, inviting people or adding credentials. Rate limits on sign-in and recovery. |
| **Passwords** | bcrypt hashed. |
| **Secrets at rest** | Provider credentials are encrypted with Fernet (`SECRET_ENCRYPTION_KEYS` supports rotation). Secrets are never returned by the API after saving. |
| **Transport** | HTTPS required in production (config checks refuse http URLs). HSTS and a strict CSP. |
| **Outgoing requests** | Website fetching blocks private, loopback, link-local and metadata addresses and re-checks every redirect (SSRF protection). |
| **Webhooks** | Provider signatures are verified (Svix, ECDSA, HMAC), timestamps are checked for freshness, and each event is stored once even if delivered again. |
| **Email compliance** | A person approves every email. Every email has one-click unsubscribe (RFC 8058) and a server-added footer. Hard bounces and complaints are suppressed across the platform. |
| **Logging** | Structured logs with request IDs. Sentry events are scrubbed of request bodies, cookies and contact details. |
| **Supply chain** | Dependabot, CodeQL, gitleaks, `pip-audit` and `npm audit` in CI. |

Production configuration is validated at startup. The API refuses to start with a weak `SECRET_KEY`, a missing encryption key, SQLite, plain-HTTP URLs, wildcard CORS or the console mailer.

## Supported versions

Only the latest release on `main` receives security fixes.
