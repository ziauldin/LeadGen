from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.email_message import EmailMessage
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.reply import Reply
from app.models.user import User
from app.schemas.reply import ReplyListResponse, ReplyRead, ReplySyncResponse, ReplyUpdate
from app.services.replies.export import export_replies_to_csv
from app.services.replies.sync import sync_mock_replies, update_reply

router = APIRouter(prefix="/replies", tags=["replies"])


def _serialize_reply(reply: Reply) -> ReplyRead:
    lead = reply.email_message.lead if reply.email_message else None
    return ReplyRead(
        id=reply.id,
        email_message_id=reply.email_message_id,
        from_email=reply.from_email,
        body=reply.body,
        classification=reply.classification,
        received_at=reply.received_at,
        lead_id=lead.id if lead else None,
        lead_name=lead.full_name if lead else None,
        campaign_id=reply.email_message.campaign_id if reply.email_message else None,
        notes=reply.notes,
    )


@router.get("", response_model=ReplyListResponse)
def list_replies(
    classification: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplyListResponse:
    query = (
        select(Reply)
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
        .options(
            selectinload(Reply.email_message).selectinload(EmailMessage.lead),
        )
    )
    count_query = (
        select(func.count(Reply.id))
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
    )

    if classification:
        query = query.where(Reply.classification == classification)
        count_query = count_query.where(Reply.classification == classification)

    total = db.scalar(count_query) or 0
    replies = db.scalars(
        query.order_by(Reply.received_at.desc()).offset(skip).limit(limit),
    ).all()

    return ReplyListResponse(
        items=[_serialize_reply(reply) for reply in replies],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch("/{reply_id}", response_model=ReplyRead)
def patch_reply(
    reply_id: int,
    payload: ReplyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplyRead:
    try:
        reply = update_reply(
            db,
            reply_id,
            current_user.id,
            classification=payload.classification,
            mark_meeting_booked=payload.mark_meeting_booked,
            notes=payload.notes,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found") from None

    db.refresh(reply, attribute_names=["email_message"])
    if reply.email_message:
        db.refresh(reply.email_message, attribute_names=["lead"])

    return _serialize_reply(reply)


@router.post("/sync", response_model=ReplySyncResponse)
def sync_replies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplySyncResponse:
    synced = sync_mock_replies(db, current_user.id)
    return ReplySyncResponse(
        synced=synced,
        message=f"Synced {synced} mock replies from sent messages.",
    )


@router.get("/export-csv")
def export_replies_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    csv_content = export_replies_to_csv(db, current_user.id)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=replies.csv"},
    )
