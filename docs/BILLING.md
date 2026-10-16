# Billing (Stripe)

Plans and their limits live in code (`services/billing/plans.py`). Stripe handles payment and keeps track of each workspace's subscription. Everything is off until `FEATURE_BILLING=true`. Until then, the plan page tells customers to contact support.

## Setup

1. **Products and prices:** in Stripe, create a product for each paid plan, with a monthly and/or yearly recurring price.
2. **API settings:**

   | Variable | Value |
   |---|---|
   | `FEATURE_BILLING` | `true` |
   | `STRIPE_SECRET_KEY` | `sk_live_…` (production refuses test keys) |
   | `STRIPE_WEBHOOK_SECRET` | `whsec_…` from the webhook endpoint below |
   | `STRIPE_PRICES` | JSON, e.g. `{"starter:month":"price_…","starter:year":"price_…","pro:month":"price_…","pro:year":"price_…"}` |
   | `STRIPE_AUTOMATIC_TAX` | `true` to use Stripe Tax (collects billing address at checkout) |
   | `BILLING_TRIAL_DAYS` | Starter trial length for new sign-ups (default `14`, `0` turns trials off) |
   | `BILLING_GRACE_DAYS` | Days a failed payment is tolerated before sending pauses (default `7`) |

3. **Webhook endpoint:** add `https://<api>/billing/webhooks/stripe` and subscribe it to these events:
   - `checkout.session.completed`
   - `customer.subscription.created`, `customer.subscription.updated` and `customer.subscription.deleted`
   - `invoice.paid` and `invoice.payment_failed`
4. **Customer portal:** turn it on in Stripe (Settings → Billing → Customer portal). Allow plan switching between your prices, card updates, invoice history and cancellation.

## How it works

- **Checkout:** owners (`billing.manage`) choose a plan under **Settings → Plan & usage**. A Stripe customer is created once per workspace, and the browser is sent to Stripe Checkout. The workspace id travels in `client_reference_id` and in the metadata.
- **Webhooks:**
  - Each event's signature is checked (`Stripe-Signature`, 5-minute tolerance).
  - Each event is stored once in `billing_events`, so retries are harmless.
  - The subscription is then **re-read from the Stripe API** and reconciled, so events arriving out of order can't leave a stale plan.
  - When Stripe's API is unreachable, the endpoint returns `503`, so Stripe retries.
- **How the subscription status changes the plan:**

  | Status | Effect on the workspace |
  |---|---|
  | `active`, `trialing` | Gets the plan for its price, and any trial ends |
  | `past_due` | Keeps its plan; the grace period starts |
  | `canceled`, `unpaid`, `incomplete_expired` | Drops to Free |

- **Trials:** new personal workspaces start on Starter for `BILLING_TRIAL_DAYS`. The hourly `billing.daily` task returns expired trials to Free unless they've subscribed.
- **Dunning:**
  - A failed payment shows a banner on every page.
  - After `BILLING_GRACE_DAYS`, `billing.daily` pauses sending with the reason "Payment overdue". Drafts and approvals keep working.
  - The pause lifts automatically when payment succeeds.
  - Suspensions made by an admin are never lifted by a payment.
- **Overrides:** admins can still set per-workspace limit and feature overrides (see `docs/ADMIN.md`). These apply on top of whatever plan Stripe sets.
- **Invoices** are listed in the app from Stripe and link to Stripe's hosted invoice pages.

## What customers pay for

Customers can connect their own keys: mailboxes or a sending service, an AI model, ZeroBounce or NeverBounce, and Hunter. They pay those providers directly, and that usage never counts against the plan. The plan pays for the product: sequences with approval, deliverability guardrails, the inbox, deals, A/B tests, analytics, integrations, seats, connected mailboxes and compliance.

Customers who don't bring a key can use the platform's keys (`PLATFORM_LLM_*`, `PLATFORM_VERIFICATION_*`, `HUNTER_*`). That usage counts first against the plan's monthly or daily allowance, then against **credits**.

## Credits

**What a credit buys:** one platform email verification, one platform email lookup, or 1,000 platform AI tokens. The cost is rounded up per request.

**How they're used:**
- They're only used once the plan's allowance for that metric is spent, and never for usage on the workspace's own keys.
- When the allowance and credits are both used up, the action is refused with `402 quota_exceeded`, as before.

**Where they're recorded:**
- **Balance:** the balance is `workspaces.credit_balance`.
- **The ledger:** every change goes into `credit_transactions`. That's purchases, grants, and one usage row per metric per day.
- **For customers:** they see their balance, the packs and recent activity under **Settings → Plan & usage → Credits**.

**Buying packs:**
- Packs are one-off Stripe payments. `CREDIT_PACKS` sets the packs and their display prices; `STRIPE_CREDIT_PRICES` maps each pack size to a Stripe one-time price, e.g. `{"1000": "price_…"}`.
- A pack without a Stripe price is shown but can't be bought online.
- Credits are added when `checkout.session.completed` (or `checkout.session.async_payment_succeeded`) arrives for a paid session. The session is re-read from Stripe before anything is added.
- Each session is applied at most once, keyed by the session id.
- Purchased credits don't expire.

**Support grants:** super-admins can add or remove credits with `POST /admin/workspaces/{id}/credits` (`{"amount", "note"}`). Every grant is audited.

## Testing locally

Use test keys and the Stripe CLI: `stripe listen --forward-to localhost:8000/billing/webhooks/stripe` prints the webhook secret to use. Test card: `4242 4242 4242 4242`. `tests/test_billing.py` covers the full flow against a fake Stripe client with signed webhook payloads.
