"""Shared consumer mailbox providers. Suppressing one of these as a domain would block everyone."""

FREEMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "hotmail.co.uk",
        "live.com",
        "live.co.uk",
        "msn.com",
        "yahoo.com",
        "yahoo.co.uk",
        "ymail.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "gmx.de",
        "mail.com",
        "zoho.com",
        "yandex.com",
        "btinternet.com",
        "sky.com",
        "virginmedia.com",
    },
)


def is_freemail_domain(domain: str) -> bool:
    return domain.strip().lower().lstrip("@") in FREEMAIL_DOMAINS
