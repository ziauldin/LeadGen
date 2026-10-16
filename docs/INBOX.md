# Unified inbox

`/inbox` shows one conversation per person, across every mailbox and campaign.

- **How conversations start:** a conversation is created the first time someone replies, keyed by their lead (or by their address when a reply couldn't be matched). Replies that arrived before the inbox existed are added the first time the inbox is opened.
- **What a thread shows:** every email sent to the lead and every reply, in time order. Each reply carries its label: positive, objection, unsubscribe and so on.
- **Views:** Open, Mine, Unassigned, Snoozed and Done, plus search by name, email or subject.
- **Actions** (need `replies.manage`):
  - Assign to a teammate
  - Snooze until tomorrow 09:00 or next week; snoozes wake every 5 minutes through the `inbox.wake_snoozed` task, and the conversation comes back unread
  - Add or remove labels (up to 10)
  - Mark done or reopen
  - A new reply always reopens the conversation
- **Replying:**
  - The reply goes to the person's last message, from the mailbox that originally emailed them, in the same thread (`In-Reply-To`/`References`).
  - It counts towards the monthly send quota.
  - People who opted out or are on the suppression list can't be replied to.
  - To answer an unmatched reply, link it to a lead first on the Replies page.
- **AI suggestions:** **Suggest a reply** drafts an answer from the conversation and your product description, when AI writing is on. A person always edits and sends it.
- **Keyboard:**

  | Key | Action |
  |---|---|
  | `j` / `k` | Next / previous conversation |
  | `r` | Reply |
  | `Ctrl+Enter` | Send |
  | `e` | Done or reopen |
  | `s` | Snooze until tomorrow |
  | `a` | Assign to me |
  | `u` | Mark unread |

API: `GET /inbox/conversations`, `GET|PATCH /inbox/conversations/{id}`, `POST /inbox/conversations/{id}/reply`, `POST /inbox/conversations/{id}/suggest`.
