# 0005: Frontend API types generated from OpenAPI

**Status:** accepted

**Context.** When frontend types are hand-written, they drift from the API. Drift showed up as real bugs, for example search results being saved with the wrong field.

**Decision.** `npm run gen:api` exports the API's OpenAPI schema and generates `src/lib/api/schema.d.ts`. In the exported schema, response-only models have every field marked required, because the API always serialises all fields. CI fails if the committed types are stale.

**Consequences.** API changes need a regeneration step, and type errors point straight at affected pages.
