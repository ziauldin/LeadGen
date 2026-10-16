"""Rule-based reply classification. Unsubscribe intent always wins (compliance first)."""

from __future__ import annotations

import re

from app.models.enums import ReplyClassification as C

_UNSUBSCRIBE = (
    "unsubscribe",
    "not relevant",
    "remove me",
    "take me off",
    "stop emailing",
    "stop contacting",
    "do not contact",
    "don't contact",
    "dont contact",
    "opt out",
    "opt-out",
    "no more emails",
)
_BOUNCE = ("undeliverable", "delivery failed", "delivery has failed", "address not found")
_WRONG_PERSON = (
    "wrong person",
    "no longer work",
    "no longer with",
    "left the company",
    "not the right person",
    "not the person you",
    "i'm not responsible",
    "i am not responsible",
)
_OBJECTION = (
    "not interested",
    "no thanks",
    "no thank you",
    "we already have",
    "we already use",
    "not a priority",
    "no budget",
)
_POSITIVE = (
    "interested",
    "sounds interesting",
    "keen to",
    "would love to",
    "happy to chat",
    "sounds good",
    "let's talk",
    "lets talk",
    "book a call",
    "set up a call",
    "schedule a call",
    "send me more",
    "tell me more",
    "free on",
    "available on",
    "calendar",
)
_NEUTRAL = ("not now", "maybe later", "busy", "reach out later", "next quarter", "next year")
_OOO = re.compile(
    r"\b(out of (the )?office|on (annual |parental |maternity )?leave|away until|"
    r"automatic reply|auto[- ]?reply)\b",
)


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", text) for p in phrases)


def classify_reply(
    body: str,
    subject: str | None = None,
    *,
    is_auto_reply: bool = False,
) -> tuple[C, float]:
    text = f"{subject or ''}\n{body}".lower()

    if _has(text, _UNSUBSCRIBE):
        return C.UNSUBSCRIBE, 0.95
    if _has(text, _BOUNCE):
        return C.BOUNCE, 0.9
    if _OOO.search(text):
        return C.OUT_OF_OFFICE, 0.9
    if is_auto_reply:
        return C.AUTO_REPLY, 0.85
    if _has(text, _WRONG_PERSON):
        return C.WRONG_PERSON, 0.8
    if _has(text, _OBJECTION):
        return C.OBJECTION, 0.8
    # A body that starts with a plain "yes" counts; the subject line comes first in ``text``.
    if _has(text, _POSITIVE) or re.search(r"^\s*(yes|sure|ok|okay)\b", body.lower()):
        return C.POSITIVE, 0.7
    if _has(text, _NEUTRAL):
        return C.NEUTRAL, 0.6
    return C.UNKNOWN, 0.0


def classify_reply_body(body: str) -> C:
    """Backwards-compatible helper."""
    return classify_reply(body)[0]
