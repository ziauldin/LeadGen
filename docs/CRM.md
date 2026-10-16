# Deals, tasks and notes (CRM-lite)

Turn it on with `FEATURE_CRM=true`, or per workspace from the admin area. **Deals** and **Tasks** then appear in the sidebar, and lead pages get an **Activity** panel.

## Deals

- **Stages:** each workspace starts with Interested (10%), Meeting booked (30%), Proposal (60%), Negotiation (80%), Won and Lost. Admins can rename stages and change probabilities. New stages are added before Won and Lost.
- **The board:** shows deal count and value per stage, and the weighted pipeline (value × stage probability).
- **Moving deals:** drag a card to another column, or use the card's stage menu (keyboard and screen reader friendly). Moving a deal to Won or Lost records when it closed.
- **Deals from replies:** an interested reply opens a deal for that lead automatically (source "from a reply"), unless the lead already has an open deal. Turn this off under **Settings → Workspace → Meetings and deals**.
- **Deal details:** each deal has a value and currency, an owner, an expected close date and an optional lead or company. Every create and move is written to the audit log and appears on the lead's timeline.

## Tasks

- Tasks have a title, a due date, an assignee (you, by default) and an optional link to a lead or deal.
- Views: **My tasks**, **Overdue**, **Everyone's** and **Done**. Lead pages show only that lead's tasks.
- When a task becomes due, the `crm.task_reminders` beat task (every 5 minutes) sends one `task_due` notification to the assignee, in the app and by email, according to their notification settings.

## Notes and the timeline

Notes belong to a lead and, optionally, a deal. Only the author or an admin can delete a note.

The lead **Timeline** merges, newest first:

- emails sent, bounced or marked as spam
- replies
- notes
- tasks created and completed
- deals opened and moved
- status changes from the audit log

## Meeting link

Set a booking link (Calendly, Cal.com…) under **Settings → Workspace → Meetings and deals** to use `{{meeting_link}}` in templates. It's a workspace-wide link, alongside the sender name and company, because campaigns send as the workspace sender. It must be an `https://` URL.

## API

| Method | Path |
|---|---|
| GET | `/deals/board` |
| POST | `/deals` |
| PATCH, DELETE | `/deals/{id}` |
| POST | `/deals/stages` |
| PATCH | `/deals/stages/{id}` |
| GET, POST | `/tasks` |
| PATCH, DELETE | `/tasks/{id}` |
| GET, POST | `/leads/{id}/notes` |
| DELETE | `/notes/{id}` |
| GET | `/leads/{id}/timeline` |
| GET | `/workspaces/current/flags` (which optional features are on) |
