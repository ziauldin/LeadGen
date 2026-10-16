# A/B tests and analytics

## A/B tests

Any campaign step can have up to three extra versions (B, C and D) alongside the main one (A). Add them under **A/B test** in the step editor. A new version starts as a copy of the step's current subject and body, so you only change what you want to test.

- **The split:** leads are spread evenly across the versions. The choice is based on the enrollment, so a lead always gets the same version of a step, even if the email is redrafted.
- **What a version contains:** its own subject and body. Every version must include `{{unsubscribe_link}}` and may only use the usual variables.
- **With saved templates:** version A uses the template; the other versions use their own text.
- **With "Write with AI":** each version's text is the fallback for its AI drafts.
- **Tracking:** every email records which version it used (`email_messages.variant`). Emails from steps without versions have no variant and count as A.

Results appear on the campaign's **Overview** tab once a step with more than one version has sent emails. For each version you see sends, reply rate, interested rate and bounce rate.

### Choosing a winner

A winner is suggested only when both of these are true:

1. Every version of the step has at least 30 sends.
2. The best version's reply rate beats the runner-up's, and a two-sided two-proportion z-test gives p < 0.05.

The result is a suggestion. It never changes the campaign. To use the winner, delete the losing versions, or copy the winner's text into version A.

## Analytics page

Turn it on with `FEATURE_ANALYTICS_V2=true`, or per workspace from the admin area. **Analytics** then appears in the sidebar.

- **Ranges:** the last 7, 30 or 90 days.
- **Totals:** emails sent, reply rate, interested rate and bounce rate. Auto-replies are left out.
- **Day by day:** sent, replies, interested and bounced per day. Replies are counted on the day they arrive.
- **Breakdowns:** by campaign, step, A/B version, mailbox and template. In these breakdowns, a reply counts towards the email it answers.
- **CSV export:** daily totals for the selected range. Needs the `data.export` permission.

## Weekly report

When the flag is on, the Monday weekly digest (see [NOTIFICATIONS.md](NOTIFICATIONS.md)) gains:

- reply, interested and bounce rates
- the best campaign (at least 10 sends)
- any A/B winners
- a link to the Analytics page

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/analytics/overview?days=30&campaign_id=` | Behind the flag |
| GET | `/analytics/export?days=30` | CSV, behind the flag |
| GET | `/campaigns/{id}/variants` | Always on: part of the campaign page |

Steps accept `variants: [{"key": "B", "subject_template": "…", "body_template": "…"}]` on campaign create and update.
