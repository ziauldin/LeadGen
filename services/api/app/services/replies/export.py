import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_message import EmailMessage
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.reply import Reply


def export_replies_to_csv(db: Session, user_id: int) -> str:
    replies = db.scalars(
        select(Reply)
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == user_id)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead))
        .order_by(Reply.received_at.desc()),
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "from_email",
            "lead_name",
            "lead_id",
            "classification",
            "received_at",
            "notes",
            "body",
        ],
    )

    for reply in replies:
        lead = reply.email_message.lead if reply.email_message else None
        classification = (
            reply.classification.value
            if hasattr(reply.classification, "value")
            else str(reply.classification)
        )
        writer.writerow(
            [
                reply.id,
                reply.from_email,
                lead.full_name if lead else "",
                lead.id if lead else "",
                classification,
                reply.received_at.isoformat(),
                reply.notes or "",
                reply.body,
            ],
        )

    return buffer.getvalue()
