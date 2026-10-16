"""Checks every AI draft must pass before a person sees it.

The model is told the rules; these checks make sure it followed them. A draft that fails is
retried once with the problems listed, then the step falls back to its template.
"""

from __future__ import annotations

import re

MAX_SUBJECT_CHARS = 80
MAX_BODY_WORDS = 150

BANNED_PHRASES = (
    "act now",
    "limited time",
    "guarantee",
    "guaranteed",
    "risk-free",
    "risk free",
    "100%",
    "click here",
    "buy now",
    "special offer",
    "no obligation",
    "once in a lifetime",
    "as seen on",
    "dear sir",
    "dear madam",
    "i hope this email finds you well",
    "i hope this finds you well",
)
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f900-\U0001f9ff\U00002b00-\U00002bff]",
)
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_BARE_DOMAIN = re.compile(
    r"\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|ai|co|app|dev|uk|de|fr|biz|info)\b",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"{{|}}|\[(?:first ?name|name|company|your name|role)\]", re.IGNORECASE)
_NUMBER = re.compile(r"[$£€]?\d[\d,.]*%?")
# Small plain numbers ("a 15 minute call", "next 2 weeks") are fine; statistics are not.
_SMALL_NUMBER = re.compile(r"^\d{1,2}$")
_MARKDOWN = re.compile(r"(^|\n)\s*(#{1,6}\s|[-*]\s|\d+\.\s)|\*\*|__", re.MULTILINE)


def _numbers_not_in(text: str, facts_text: str) -> list[str]:
    found = []
    for token in _NUMBER.findall(text):
        cleaned = token.rstrip(".,")
        if not cleaned or _SMALL_NUMBER.match(cleaned):
            continue
        if cleaned not in facts_text:
            found.append(cleaned)
    return found


def check_draft(subject: str, body: str, *, facts_text: str) -> list[str]:
    """Return the rule violations for a draft (empty when it passes)."""
    problems: list[str] = []
    subject = subject.strip()
    body = body.strip()
    facts_lower = facts_text.lower()

    if not subject:
        problems.append("The subject is empty")
    elif len(subject) > MAX_SUBJECT_CHARS:
        problems.append(f"The subject is longer than {MAX_SUBJECT_CHARS} characters")
    if subject.isupper() and len(subject) > 3:
        problems.append("The subject is in capitals")

    words = len(body.split())
    if words == 0:
        problems.append("The body is empty")
    elif words > MAX_BODY_WORDS:
        problems.append(f"The body is {words} words; keep it under {MAX_BODY_WORDS}")

    combined = f"{subject}\n{body}"
    lowered = combined.lower()
    if _EMOJI.search(combined):
        problems.append("Remove emoji")
    banned = [phrase for phrase in BANNED_PHRASES if phrase in lowered]
    if banned:
        problems.append(f"Remove these phrases: {', '.join(banned)}")
    if _URL.search(combined):
        problems.append("Remove links; the email must not contain URLs")
    else:
        stray = [
            m.group(0)
            for m in _BARE_DOMAIN.finditer(combined)
            if m.group(0).lower() not in facts_lower
        ]
        if stray:
            problems.append(f"Remove web addresses that are not in the facts: {', '.join(stray)}")
    if _PLACEHOLDER.search(combined):
        problems.append("Fill in or remove placeholder text such as [Name] or {{...}}")
    if _MARKDOWN.search(body):
        problems.append("Write plain text without markdown, bullet points or headings")
    invented = _numbers_not_in(combined, facts_text)
    if invented:
        problems.append(
            "Do not use numbers or statistics that are not in the facts: " + ", ".join(invented),
        )
    if "unsubscribe" in lowered or "opt out" in lowered:
        problems.append("Do not write an unsubscribe line; it is added automatically")
    return problems
