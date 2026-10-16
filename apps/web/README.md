# LeadsGen web app

Next.js 15 (App Router) front end for LeadsGen. See the [root README](../../README.md) for the product and [docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md) for hosting.

## Run locally

```bash
npm install
npm run dev        # http://localhost:3000
```

The browser calls `/api/*`, which [`next.config.ts`](next.config.ts) proxies to `API_INTERNAL_URL` (default `http://localhost:8000`). That keeps the refresh-token cookie first-party; the short-lived access token is held in memory only.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` / `build` / `start` | Develop, build, serve |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest + Testing Library + MSW |
| `npm run gen:api` | Regenerate `src/lib/api/schema.d.ts` from the API's OpenAPI schema (needs the API's Python environment) |

## Where things live

- `src/lib/api/client.ts`: fetch wrapper. It handles token refresh on 401 (one shared request), the `X-Workspace-Id` header and readable error messages.
- `src/lib/api/endpoints.ts`: typed functions for every API route. `src/lib/api/types.ts` gives friendly names to the generated types.
- `src/hooks/`:
  - `use-auth`: the session.
  - `use-workspace`: the current workspace, role checks, and switching (which clears cached data).
  - `use-table-state`: paging, sorting and filters, kept in the URL.
- `src/components/data-table/`: the server-driven table with selection and bulk actions, used by every list page.
- `src/middleware.ts`: sends signed-out visitors to `/login`, using the `lg_session` hint cookie.
- Feature folders under `src/components/`: approvals, campaigns, emails, templates, leads, replies, settings, dashboard and more.

Failed mutations show a toast with the API's message automatically. Pages show an error panel with a retry button when a query fails.
