# Marketing site and legal pages

The public site lives in the same Next.js app, under `src/app/(marketing)`:

- `/`: landing page. Signed-in visitors go straight to `/dashboard`.
- `/features`, `/use-cases`, `/about`
- `/pricing`: rendered from the API's public `GET /billing/plans` and `GET /billing/credit-packs`, and refreshed every 10 minutes. It falls back to built-in plans and packs when the API is unreachable, for example during a build. It has a monthly/yearly switch; yearly prices are shown per month.
- `/contact`: form sending to `POST /contact`. It's rate limited (5 per hour per IP) and has a honeypot field, plus Turnstile when configured. Messages go to `SUPPORT_EMAIL`.
- `/docs/api`: API reference built from `/v1/openapi.json`.
- `/legal/terms`, `/legal/privacy`, `/legal/dpa`, `/legal/acceptable-use`, `/legal/cookies`. The content lives in `src/content/legal.ts`.
- `/subprocessors`
- SEO: `sitemap.xml`, `robots.txt` (the app and admin areas are disallowed), an Open Graph image, and canonical URLs on every page.

## Settings

| Where | Variable | Purpose |
|---|---|---|
| Web | `NEXT_PUBLIC_SITE_URL` | Public site URL for canonical links, sitemap and social images |
| Web | `NEXT_PUBLIC_LEGAL_ENTITY`, `NEXT_PUBLIC_LEGAL_ADDRESS` | The company named in legal pages and the footer |
| Web | `NEXT_PUBLIC_CONTACT_EMAIL`, `NEXT_PUBLIC_PRIVACY_EMAIL` | Contact addresses shown on legal and contact pages |
| Web | `NEXT_PUBLIC_STATUS_URL` | Optional status page link in the footer |
| API | `PLAN_DISPLAY_PRICES` | Prices shown on `/pricing` ("year" is the yearly total). Default: Starter $39/month or $390/year, Pro $99/month or $990/year, Enterprise "Custom". Stripe still decides what's actually charged, so keep the two in step. |
| API | `CREDIT_PACKS` | Credit packs shown on `/pricing` and in billing settings ([BILLING.md](BILLING.md#credits)). |
| API | `SUPPORT_EMAIL` | Where contact-form messages are sent |

## Legal text

The legal pages are a solid starting point, not legal advice. **Have them reviewed by counsel for your jurisdiction before launch.** Then update `UPDATED` in `src/content/legal.ts` whenever they change.

## Look and layout

The public site uses a dark theme that only applies inside the marketing layout. The signed-in app keeps its light theme.

**Theme tokens:**
- The `mk` class on the layout (see `globals.css`) remaps the app's colour tokens to dark values, so shared components and content pages read correctly.
- It also defines the marketing palette (`--mk-*`).

**Building blocks:**
- `mk-cta` is the gradient call-to-action, with white text at AA contrast. `mk-ghost` is the secondary button.
- `mk-card` is the glass card. `mk-gradient-text` gives headline highlights.
- `mk-aurora` and `mk-grid-bg` are the decorative hero backgrounds.
- Motion classes (`mk-fade-up`, `mk-float`) are switched off under `prefers-reduced-motion`.

**Layouts:**
- The landing page and `/pricing` lay out full-width sections.
- Inner pages live in the `(content)` route group. Its layout adds the centred column and a soft glow. Their URLs are unchanged.

**Landing page sections:**
- hero with a product preview (`hero-preview.tsx`, HTML with sample data, labelled as an illustration)
- "works with" strip and product facts
- how it works, feature grid
- the estimate calculator (`roi-calculator.tsx`)
- comparison with a do-it-yourself stack
- trust, FAQ (`faq.tsx`) and a closing call to action

**Honesty rules for copy:** don't add customer logos, testimonials or usage numbers until they're real and approved for use. Product facts and integrations are fine.

## Cookies and consent

The cookie bar stores the visitor's choice (`all` or `essential`) in `localStorage`. Code that sets non-essential cookies, such as product analytics, must check `useConsent()` from `src/lib/consent.ts` and only run on `"all"`.

## Quality checks

- Playwright runs axe accessibility checks on every public page (`e2e/a11y.spec.ts`).
- Lighthouse CI (`.github/workflows/lighthouse.yml`, `apps/web/lighthouserc.json`) fails pull requests on accessibility below 95 or SEO below 90. It warns on performance and best practices.
