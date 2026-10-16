---
title: Sequences and replies
summary: How follow-ups work and what happens when someone replies.
category: Campaigns
order: 5
---

## Follow-up steps

A campaign can have several steps, each with a delay in days. After the first email is sent, the next step is drafted when its delay has passed, and goes through approval like the first.

## When a sequence stops

A lead's sequence stops automatically when:

- they reply (any reply, including out-of-office handling where configured)
- they unsubscribe or ask not to be contacted
- their address bounces or they mark the email as spam
- you stop it by hand from the campaign's enrollments list

## Replies

Replies arrive through your provider's inbound webhook or IMAP polling, and are matched to the original email. Each one is labelled (for example *interested*, *not now*, *unsubscribe*) so you can deal with the important ones first. Replies asking not to be contacted add the address to your suppression list.
