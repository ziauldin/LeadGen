# Provider setup

Each workspace connects its own providers in **Settings → Providers**. Secrets are encrypted at rest and never shown again after saving. Only one account of each type is active at a time.

## Sending accounts (outreach)

| Provider | Fields | Webhook signature |
|---|---|---|
| **Resend** | API key, from address | Svix signing secret (`whsec_…`) |
| **SendGrid** | API key, from address | Event Webhook verification key (public key) |
| **Mailgun** | API key, sending domain, from address | HTTP webhook signing key |
| **SMTP** | host, port, username, password, from address | (none; use IMAP for replies) |
| **Mock** | (none) | For trying the flow locally; nothing is delivered |

After saving a sending account:

1. **Test** it, then **Activate** it.
2. Copy the **webhook URL(s)** shown on the card into the provider's dashboard:
   - **Resend**: Webhooks, then add the URL for the `email.delivered`, `email.bounced`, `email.complained` and `email.received` events. Paste the signing secret back into LeadsGen.
   - **SendGrid**:
     - **Mail Settings → Event Webhook**: use the *events* URL with Delivered, Bounce, Dropped and Spam Report events, turn on Signed Event Webhook, and paste the verification key into LeadsGen.
     - **Inbound Parse**: point your reply domain at the *inbound* URL. Inbound Parse isn't signed; the long random token in the URL identifies your workspace.
   - **Mailgun**:
     - **Webhooks**: use the *events* URL for delivered, permanent fail, temporary fail and complained.
     - **Routes**: forward replies to the *inbound* URL.
     - Paste the webhook signing key into LeadsGen.
3. Run **Settings → Deliverability** and publish the SPF, DKIM and DMARC records your provider gives you.

Webhooks need `FEATURE_INBOUND_WEBHOOKS=true`. Each event is stored once, even if the provider retries it.

### Warm-up

New sending domains should start slowly. On an email account card, turn on **warm-up** with a starting volume, a daily increase and a maximum. LeadsGen sends no more than today's warm-up limit, and the rest waits for the next day.

### Reply addresses

If you set `INBOUND_EMAIL_DOMAIN` (for example `in.example.com`, with MX records pointing at your inbound provider):
- Each email gets a `Reply-To: reply+TOKEN@in.example.com` header, so replies match even when mail clients drop threading headers.
- `List-Unsubscribe` gets a `mailto:unsubscribe+TOKEN@…` alternative.

Without it, replies are matched by `In-Reply-To` and `References`, then the provider's message id, then the sender address (low confidence). Anything left unmatched can be linked by hand on the reply page.

## Reply inbox (IMAP)

For SMTP senders, or as a backup to webhooks. Add an **IMAP** account under *Reply inbox* with host, port (993), username, password, folder (`INBOX`) and SSL. LeadsGen polls every 5 minutes and remembers where it got to, so messages are never processed twice. Needs `FEATURE_IMAP=true`.

## AI model (optional)

Add a **Groq**, **OpenAI** or **Gemini** API key under *AI model*; the model name is optional. Without a key, the workspace uses the platform's key (if the operator configured `PLATFORM_LLM_PROVIDER`), counted against the plan's monthly AI token allowance. Turn AI on in **Settings → Workspace**, and describe what you offer there: AI drafts may only use facts from that description and the lead's data. Needs `FEATURE_AI_EMAILS=true`.

Every AI draft is checked before anyone sees it. It is retried once with feedback, and if it still fails, the step uses its template and the draft says why:
- subject at most 80 characters, body at most 150 words
- no links, emoji, placeholders or hype phrases
- no numbers that aren't in the input
- no unsubscribe line (the system adds the footer)

## Search providers

Google Programmable Search, Bing Web Search and SerpAPI are supported, plus **Mock** for local use. Add the API key (and the search engine id for Google) under *Search*. The search page lets you pick any configured provider.

## Email discovery

**Hunter.io** finds contact emails for enriched companies, within the daily lookup limit of your plan.
