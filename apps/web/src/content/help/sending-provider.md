---
title: Connect a sending provider
summary: Use Resend, SendGrid, Mailgun or SMTP to send from your own domain.
category: Sending
order: 2
---

LeadsGen never sends from a shared pool. You connect your own provider account, so you keep control of your domain's reputation.

## Choose a provider

- **Resend**: simple setup, good for most teams.
- **SendGrid** or **Mailgun**: mature options with detailed analytics.
- **SMTP**: any mail server, including Google Workspace or Microsoft 365 SMTP relay.

## Connect it

1. Go to **Settings → Providers** and choose your provider.
2. Paste the API key (or SMTP details) and the "from" address you verified with the provider.
3. Click **Test**. We send a test request without emailing anyone.
4. Click **Activate** to use it for campaigns.

Keys are encrypted at rest and never shown again after you save them.

## Turn on bounce and reply tracking

Copy the webhook URLs shown under the provider and add them in your provider's dashboard. This lets LeadsGen stop sequences when an address bounces or someone marks you as spam, and bring replies into the app.

## Warm-up

New domains should start slowly. Turn on warm-up for the provider to raise the daily limit gradually over a few weeks.
