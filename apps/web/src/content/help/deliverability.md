---
title: Set up SPF, DKIM and DMARC
summary: The three DNS records that decide whether your emails reach the inbox.
category: Sending
order: 3
---

Mailbox providers check three DNS records to decide whether an email really comes from you. **Settings → Deliverability** checks them for you.

## SPF

SPF lists the servers allowed to send for your domain. Add the include your provider gives you, for example:

```
v=spf1 include:_spf.resend.com ~all
```

Only have one SPF record per domain. Combine includes into a single record.

## DKIM

DKIM signs each email so it can't be altered on the way. Your provider gives you one or more CNAME or TXT records to add. Once DNS updates, verify the domain in the provider's dashboard.

## DMARC

DMARC tells mailbox providers what to do with emails that fail SPF or DKIM, and where to send reports. Start with monitoring only:

```
v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

Move to `p=quarantine` once reports show your legitimate email passes.

## Good habits

- Send from a subdomain such as `mail.yourcompany.com` to protect your main domain.
- Keep daily volumes modest and use warm-up on new domains.
- Remove addresses that bounce; LeadsGen does this automatically when webhooks are set up.
- Write to people who'd reasonably expect to hear from you.
