from app.models.enums import ReplyClassification


def classify_reply_body(body: str) -> ReplyClassification:
    lowered = body.lower()

    if any(
        phrase in lowered
        for phrase in ("unsubscribe", "not relevant", "remove me", "stop emailing", "opt out")
    ):
        return ReplyClassification.UNSUBSCRIBE

    if any(phrase in lowered for phrase in ("undeliverable", "bounce", "delivery failed")):
        return ReplyClassification.BOUNCE

    if any(
        phrase in lowered
        for phrase in ("yes", "interested", "happy to chat", "sounds good", "let's talk", "book a call")
    ):
        return ReplyClassification.POSITIVE

    if any(phrase in lowered for phrase in ("not now", "maybe later", "busy", "reach out later")):
        return ReplyClassification.NEUTRAL

    if any(
        phrase in lowered
        for phrase in ("not interested", "no thanks", "don't contact", "do not contact")
    ):
        return ReplyClassification.OBJECTION

    return ReplyClassification.UNKNOWN
