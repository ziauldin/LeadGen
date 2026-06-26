## Frontend app

This is the Next.js frontend for the lead-intelligence and outreach workflow system.

## Requirements

Use:

* Next.js App Router
* TypeScript
* Tailwind CSS
* shadcn/ui
* TanStack Query
* React Hook Form
* Zod

## Local development

Native local setup — no Docker required:

* `npm run dev` from `apps/web`
* Set `NEXT_PUBLIC_API_URL` in `.env.local` (defaults to `http://localhost:8000`)

## UI style

The interface should be:

* clean,
* modern,
* professional,
* light theme by default,
* responsive,
* data-table friendly,
* easy for a founder/operator to use.

Avoid:

* gimmicky animations,
* cluttered dashboards,
* dark-pattern conversion UI,
* fake urgency,
* spam-focused wording.

## Main pages

Create these routes:

* /login
* /register
* /dashboard
* /niches
* /niches/[id]
* /search
* /leads
* /leads/[id]
* /companies
* /campaigns
* /campaigns/[id]
* /email-studio
* /replies
* /settings

## Main layout

Use:

* left sidebar navigation,
* top bar,
* responsive content area,
* reusable page header,
* reusable loading/error states.

## Components

Create reusable components for:

* LeadTable
* LeadStatusBadge
* ScoreBadge
* CompanyCard
* NicheForm
* SearchQueryBuilder
* SearchResultsTable
* EmailPreview
* CampaignStepEditor
* ReplyClassificationBadge
* EmptyState
* ConfirmDialog

## API access

Use a typed API client.

Keep API calls in:

* /lib/api
* /hooks

Use TanStack Query for server state.

Do not hardcode backend URLs. Use environment variables.

## Forms

Use React Hook Form and Zod validation.

Validate:

* niche creation,
* lead creation,
* campaign creation,
* email approval,
* settings forms.

## Outreach UX rules

Before showing a "send" action:

* confirm lead has an email,
* confirm lead is not opted out,
* confirm lead is not suppressed,
* confirm source URL exists,
* confirm compliance/source note exists,
* confirm email has been manually approved.

Do not create one-click mass sending without review.
