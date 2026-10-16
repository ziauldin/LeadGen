import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_message import EmailMessage
from app.models.reply import Reply
from app.services.common.csv_safety import safe_cell


def export_replies_to_csv(db: Session, workspace_id: int) -> str:
    replies = db.scalars(
        select(Reply)
        .where(Reply.workspace_id == workspace_id)
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
                safe_cell(value)
                for value in (
                    reply.id,
                    reply.from_email,
                    lead.full_name if lead else "",
                    lead.id if lead else "",
                    classification,
                    reply.received_at.isoformat(),
                    reply.notes or "",
                    reply.body,
                )
            ],
        )

    return buffer.getvalue()
