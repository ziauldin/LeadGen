---
title: API keys and webhooks
summary: Connect LeadsGen to your CRM, Zapier or your own code.
category: Integrations
order: 8
---

API keys and webhooks are available on Starter and above, under **Settings → API & webhooks**.

## API keys

Create a key, choose its scopes (for example *Read leads* and *Create and update leads*) and copy it. It's only shown once. Keys act with your permissions and stop working if you leave the workspace.

See the [API reference](/docs/api) for endpoints.

## Webhooks

Add a URL and choose events such as `reply.received` or `lead.created`. We send a signed JSON request each time. Verify the `LeadsGen-Signature` header with your endpoint's signing secret.

Use **Test** to send a sample event, and **Deliveries** to see recent attempts and replay any that failed.

## Zapier and Make

Use a "Catch hook" or "Webhooks" trigger, paste its URL as a LeadsGen webhook endpoint, and pick the events you want.
