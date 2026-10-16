# Subprocessors

This list is shown publicly at `/subprocessors`. Its source of truth is `apps/web/src/lib/subprocessors.ts`. Give customers 30 days' notice before adding a platform subprocessor.

## Platform

| Subprocessor | Purpose | Personal data | Location | Used |
|---|---|---|---|---|
| Railway | Hosting, database, queues | All workspace data | US / EU | Always |
| AWS S3 or Cloudflare R2 | Export and attachment storage | Export files | Operator's region | When object storage is configured |
| Sentry | Error monitoring | Error details, user/workspace IDs | US | When `SENTRY_DSN` is set |
| Cloudflare Turnstile | Bot protection | IP, browser signals | Global | When `TURNSTILE_SECRET_KEY` is set |
| Platform SMTP provider | Account emails | Account holder name and email | Provider's region | Always |

## Chosen by each workspace

| Subprocessor | Purpose | Personal data | Used |
|---|---|---|---|
| Resend, SendGrid, Mailgun, or the workspace's SMTP server | Sending outreach | Recipient email, name, email content | The sending provider connected |
| OpenAI, Google Gemini, Groq | AI drafting and reply classification | Lead profile fields, reply text | Only with AI on and a key added |
| Hunter | Email finding and checks | Name, company domain | Only if connected |
| Google Programmable Search, Bing, SerpAPI | Finding public listings | Search queries only | Only if connected |
