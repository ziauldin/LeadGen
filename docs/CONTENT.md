# Help center, blog, changelog, analytics and feedback

## Writing content

| What | Where | URL |
|---|---|---|
| Help articles | `apps/web/src/content/help/*.md` | `/help`, `/help/<file name>` |
| Blog posts | `apps/web/src/content/blog/*.md` | `/blog`, `/blog/<file name>` |
| Changelog | `apps/web/src/content/changelog.ts` (newest first) | `/changelog`, plus **What's new** in the app |

Markdown files start with frontmatter:

```markdown
---
title: Set up SPF, DKIM and DMARC
summary: One sentence shown in lists and search results.
category: Sending        # help only: groups articles on /help
order: 3                 # help only: position within the list
date: 2026-10-01         # blog only
author: The LeadsGen team
---
```

The body supports `##`–`####` headings, paragraphs, bullet and numbered lists, `>` quotes, fenced code blocks, `**bold**`, `*italic*`, `` `code` `` and `[links](/path)`. It's rendered by `src/lib/markdown.tsx`, which builds React elements and never outputs raw HTML.

Pages are generated at build time, and new files appear in `sitemap.xml` automatically. The help center has instant client-side search over titles, summaries and categories.

Adding an entry to the top of `CHANGELOG` shows a dot on the **?** menu in the app until each person opens **What's new**. Their last-seen entry is remembered in their browser.

## Product analytics (PostHog)

PostHog is off unless `NEXT_PUBLIC_POSTHOG_KEY` is set. Optionally set `NEXT_PUBLIC_POSTHOG_HOST` (default `https://eu.i.posthog.com`). Even when configured, it only loads after the visitor chooses **Accept all** in the cookie banner. These protections apply:

- No autocapture and no session recording; text is masked.
- People are identified by numeric user id, never by email or name, and grouped by workspace (with the plan as a property).
- Impersonation sessions are never tracked.
- Choosing **Essential only** opts out.

Funnel events, from `src/lib/analytics.ts` (keep the names stable):

| Event | When |
|---|---|
| `signed_up` | Registration succeeded |
| `email_verified` | The verification link was confirmed |
| `campaign_created` | A campaign was created |
| `checkout_started` | An owner started Stripe Checkout (`plan`, `interval`) |
| `feedback_sent` | Feedback was sent (`kind`) |

`provider_connected`, `emails_approved` and `first_send` are reserved names for the same funnel.

## Feedback

**? → Send feedback** in the app posts to `POST /feedback` (signed-in only, 20 per hour per user). The message is emailed to `SUPPORT_EMAIL` with the person's id, email, workspace and the page they were on.
