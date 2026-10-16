# 0003: Every outreach email needs human approval

**Status:** accepted

**Context.** Automated cold email is easy to abuse and damages sender reputation and recipients' trust. AI drafting makes high volume even easier.

**Decision.** Nothing is sent unless a person has approved it. This includes AI drafts and automatic follow-ups, which are created as `pending_approval`.

The send gate re-checks the following at send time:
- suppression
- opt-out
- the lead source and compliance note
- sequence state

AI drafts must pass guardrails and fall back to templates when they don't.

**Consequences.**
- The approval queue is a core product surface and has to be fast to use, with keyboard shortcuts and bulk actions.
- Throughput is limited by review capacity. That is intended.
