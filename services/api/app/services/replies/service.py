"""Manual reply updates (classification, notes, meeting booked)."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_message import EmailMessage
from app.models.enums import LeadStatus, ReplyClassification
from app.models.lead import Lead
from app.models.reply import Reply


def update_reply(
    db: Session,
    reply_id: int,
    workspace_id: int,
    classification: ReplyClassification | None = None,
    mark_meeting_booked: bool = False,
    notes: str | None = None,
) -> Reply:
    reply = db.scalar(
        select(Reply)
        .where(Reply.id == reply_id, Reply.workspace_id == workspace_id)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead)),
    )
    if reply is None:
        raise ValueError("Reply not found")

    if classification is not None:
        reply.classification = classification
        reply.classified_by = "user"
        reply.classification_confidence = 1.0
    if notes is not None:
        reply.notes = notes

    lead = reply.email_message.lead if reply.email_message else None
    if lead is None and reply.lead_id is not None:
        lead = db.get(Lead, reply.lead_id)
    if mark_meeting_booked and lead:
        lead.status = LeadStatus.MEETING_BOOKED
    elif classification == ReplyClassification.POSITIVE and lead:
        lead.status = LeadStatus.REPLIED

    db.commit()
    db.refresh(reply)
    return reply
