"""Reply text helpers: strip quoted history and spot automatic replies."""

from __future__ import annotations

import re
from collections.abc import Mapping

_QUOTE_HEADERS = [
    re.compile(r"^On .{3,200}wrote:\s*$", re.IGNORECASE),
    re.compile(r"^Le .{3,200}a écrit\s*:\s*$", re.IGNORECASE),
    re.compile(r"^Am .{3,200}schrieb .{0,100}:\s*$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^_{5,}\s*$"),
    re.compile(r"^From:\s.+", re.IGNORECASE),
]
_SIGNATURE_MARKERS = (re.compile(r"^--\s*$"), re.compile(r"^Sent from my ", re.IGNORECASE))

_AUTO_SUBJECT = re.compile(
    r"^(out of (the )?office|automatic reply|auto(matic)?[- ]?reply|autoreply|auto:|"
    r"away from (the )?office|on leave|abwesend|absence)",
    re.IGNORECASE,
)
_OOO_BODY = re.compile(
    r"\b(out of (the )?office|on (annual |parental |maternity )?leave|away until|"
    r"limited access to (my )?email|back (in the office )?on)\b",
    re.IGNORECASE,
)


def strip_quoted(text: str) -> str:
    """Return only the new part of a reply."""
    kept: list[str] = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if any(pattern.match(stripped) for pattern in _QUOTE_HEADERS):
            break
        if any(pattern.match(stripped) for pattern in _SIGNATURE_MARKERS):
            break
        kept.append(line)
    result = "\n".join(kept).strip()
    return result or (text or "").strip()


def is_auto_reply(headers: Mapping[str, str], subject: str | None) -> bool:
    lowered = {key.lower(): str(value).lower() for key, value in headers.items()}
    auto_submitted = lowered.get("auto-submitted")
    if auto_submitted and auto_submitted != "no":
        return True
    if (
        "x-autoreply" in lowered
        or "x-autorespond" in lowered
        or "x-auto-response-suppress" in lowered
    ):
        return True
    if lowered.get("precedence") in {"auto_reply", "bulk", "junk", "list"}:
        return True
    return bool(subject and _AUTO_SUBJECT.match(subject.strip()))


def looks_out_of_office(subject: str | None, body: str) -> bool:
    return bool(
        (subject and _AUTO_SUBJECT.match(subject.strip())) or _OOO_BODY.search(body[:2000]),
    )


def is_bounce_report(from_email: str, subject: str | None, content_type: str | None) -> bool:
    sender = from_email.lower()
    if content_type and "multipart/report" in content_type.lower():
        return True
    if sender.startswith(("mailer-daemon@", "postmaster@")):
        return True
    return bool(
        subject
        and re.match(
            r"^(undeliver(able|ed)|delivery status notification|mail delivery failed|returned mail)",
            subject.strip(),
            re.IGNORECASE,
        ),
    )
