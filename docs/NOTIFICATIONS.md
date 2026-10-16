# Onboarding, notifications and lifecycle emails

## Onboarding

New workspaces see a **Get set up** checklist on the dashboard. Its **Open setup guide** button opens `/onboarding`, a step-by-step guide:

1. Verify your email
2. Add your sender details
3. Connect an email provider
4. Check your domain's DNS (recommended)
5. Create a niche
6. Add your first leads
7. Create a campaign

Steps tick themselves off from `GET /workspaces/current/onboarding` when the person comes back to the page. They can also skip ahead.

## Notifications

The bell in the top bar polls `GET /notifications` every 30 seconds and shows the unread count. Opening a notification marks it read. Everyone chooses their channels under **Settings → Notifications**.

| Kind | Who gets it | Default |
|---|---|---|
| `positive_reply`: someone replies with interest | Everyone in the workspace | App and email |
| `campaign_paused`: auto-paused for bounces or complaints | Owners and admins | App and email |
| `payment_failed` | Owners | App and email |
| `trial_ending`: 3 days before | Owners | App and email |
| `member_joined` | Owners and admins | App |
| `data_request_done` | The person who asked | App |
| `weekly_digest` | Owners and admins | Email |

Raise a new notification from service code with `services.notifications.events` (best effort; it never breaks the caller) or `notify(db, workspace_id, kind, title, ...)`.

## Slack

Under **Settings → Notifications → Slack**, admins (`settings.manage`) paste an incoming-webhook URL:

- Only `https://hooks.slack.com/services/...` is accepted, and the URL is stored encrypted.
- They choose which kinds to post: interested replies, auto-paused campaigns, failed payments and new members.
- Messages are posted by the `notifications.slack` task through the SSRF-safe client. **Send a test message** checks the connection.

## Lifecycle emails

Each email below is sent at most once per person. The `lifecycle_emails` table records what was sent.

| Email | When |
|---|---|
| Welcome | The first time someone confirms their email |
| Verification reminder | Once, 24 hours after sign-up, if still unverified (within the first week) |
| Trial ending | 3 days before the trial ends, to owners |
| Weekly digest | Mondays at 08:00 UTC, to owners and admins of workspaces with activity in the last 7 days: emails sent, replies (and how many interested), new leads |

Beat runs `notifications.daily` (hourly; idempotent) and `notifications.weekly_digest` (cron, Monday 08:00 UTC). Payment-failed and campaign-paused emails go out as notifications, as soon as they happen.
