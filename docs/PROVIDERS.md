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

## Mailboxes: Gmail and Microsoft 365 (OAuth)

Turn this on with `FEATURE_MAILBOX_OAUTH=true`, or for one workspace from the admin area. People connect their own inboxes under **Settings → Providers → Mailboxes**. LeadsGen then sends through the Gmail API or Microsoft Graph, and syncs replies from the same mailbox.

**Operator setup.** It reuses the OAuth apps from "Continue with Google / Microsoft" (`GOOGLE_OAUTH_CLIENT_ID/SECRET`, `MICROSOFT_OAUTH_CLIENT_ID/SECRET`).

- **Redirect URIs:** add `https://<web>/api/mailboxes/oauth/gmail/callback` and `https://<web>/api/mailboxes/oauth/outlook/callback`.
- **Google:** enable the Gmail API. Add the scopes `gmail.send` and `gmail.readonly`. These are *restricted* scopes:
  - Until the app passes Google's OAuth verification and the CASA security assessment, only the test users listed on the consent screen can connect (up to 100).
  - Plan for the verification before a public launch.
- **Microsoft:** add the delegated Graph permissions `Mail.Send`, `Mail.Read`, `User.Read` and `offline_access`. Complete publisher verification so tenants don't see an "unverified" warning. Some tenants also need an admin to consent.

**How it works**

- **Connecting:** uses the authorization code flow with PKCE. The short-lived state is signed and carries the encrypted PKCE verifier. Refresh tokens are stored encrypted, and access tokens refresh automatically. Microsoft's rotated refresh tokens are saved too.
- **Sending:** each email goes out as a full MIME message, so our `Message-ID`, `In-Reply-To` and `References` headers survive and threads stay intact.
- **Reply sync:** runs every 5 minutes with the inbox poll, using Gmail history and the Graph delta query. The first sync only records a starting point; old mail isn't imported. New messages go through the normal reply pipeline (matching, labelling, stopping sequences).
- **Limits:** new mailboxes start with warm-up on and a daily limit of 50, which can be changed per mailbox. The send gate uses the lower of the warm-up cap and the daily limit.
- **Health:** a mailbox is paused when more than 8% of its last 50 sends bounce, or more than 0.5% are marked as spam (after at least 20 sends). Revoked access marks it **Reconnect needed**, and paused mailboxes are skipped. Admins can resume a mailbox paused for health. Reconnecting fixes an access problem.

**Rotation.** On a campaign's **Sequence** tab, choose several sending accounts:

- Each new lead's first email goes from the healthy account with the most room left today.
- Follow-ups always come from the mailbox that sent that lead's first email.
- With no accounts selected, the campaign uses its default sender, as before.

## Email verification

Under **Providers → Email verification**, connect **ZeroBounce** or **NeverBounce** with an API key (or the test verifier).

Each contact gets a verification status:

| Status | Meaning |
|---|---|
| `valid` | The mailbox exists |
| `risky` | Catch-all, disposable or abuse addresses |
| `invalid` | Bad syntax, no mail server, the mailbox doesn't exist, or a spam trap |
| `unknown` | The check couldn't decide |

- **When contacts are checked:** with a provider connected, new contacts are checked in the background after CSV imports and when leads are added to a campaign. Anyone can also select leads and choose **Verify emails**. Without a provider, **Verify emails** runs a free DNS-only check (syntax, disposable domains, and whether the domain accepts mail at all), which can mark addresses invalid but never valid.
- **What gets blocked:** the approval checks and the send gate never email `invalid` addresses. Turn on **Settings → Deliverability → Don't send to risky addresses** to block `risky` ones too.
- **Who pays:** checks on the workspace's own ZeroBounce or NeverBounce key are paid to that provider and never count against the plan. Without a key, the operator can offer platform verification (`PLATFORM_VERIFICATION_PROVIDER` and `PLATFORM_VERIFICATION_API_KEY`); each of those checks uses one of the plan's `monthly_verifications` (Free 100, Starter 2,000, Pro 20,000, Enterprise 100,000). DNS-only checks and provider errors are always free. Results older than 90 days are re-checked when verified again.

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
