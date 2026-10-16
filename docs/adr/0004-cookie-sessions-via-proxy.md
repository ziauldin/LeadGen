# 0004: First-party refresh cookie through a Next.js /api proxy

**Status:** accepted

**Context.** Storing tokens in `localStorage` exposes them to XSS. Cross-site cookies between separate web and API domains need `SameSite=None` and are increasingly blocked by browsers.

**Decision.**
- The browser only talks to the web origin; Next.js rewrites `/api/*` to the API over the private network.
- The refresh token is an httpOnly, `SameSite=Lax` cookie scoped to `/api/auth`.
- The access token lasts 15 minutes and lives in memory. A 401 triggers one shared refresh.
- A non-secret `lg_session` cookie lets the middleware redirect signed-out visitors.

**Consequences.**
- `API_INTERNAL_URL` is fixed into the rewrite at build time.
- Refreshing requires an `X-Requested-With` header, as a CSRF defence.
