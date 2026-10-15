from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.core.config import settings
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.email_message import EmailMessage
from app.models.reply import Reply
from app.schemas.reply import ReplyListResponse, ReplyRead, ReplySyncResponse, ReplyUpdate
from app.services.replies.export import export_replies_to_csv
from app.services.replies.sync import sync_mock_replies, update_reply
from app.services.sending.provider_factory import is_mock_email_provider_active

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
    classification: str | None = Query(default=None, max_length=50),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ReplyListResponse:
    conditions = [Reply.workspace_id == ctx.workspace_id]
    if classification:
        conditions.append(Reply.classification == classification)

    total = db.scalar(select(func.count(Reply.id)).where(*conditions)) or 0
    replies = db.scalars(
        select(Reply)
        .where(*conditions)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead))
        .order_by(Reply.received_at.desc(), Reply.id.desc())
        .offset(skip)
        .limit(limit),
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
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ReplyRead:
    try:
        reply = update_reply(
            db,
            reply_id,
            ctx.workspace_id,
            classification=payload.classification,
            mark_meeting_booked=payload.mark_meeting_booked,
            notes=payload.notes,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found"
        ) from None

    db.refresh(reply, attribute_names=["email_message"])
    if reply.email_message:
        db.refresh(reply.email_message, attribute_names=["lead"])

    return _serialize_reply(reply)


@router.post("/sync", response_model=ReplySyncResponse)
def sync_replies(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ReplySyncResponse:
    """Development helper: simulate replies to emails sent with the mock provider.

    Real replies arrive through provider webhooks or the IMAP inbox poller.
    """
    if settings.is_production or not is_mock_email_provider_active(db, ctx.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reply simulation is only available with the mock email provider in development.",
        )
    synced = sync_mock_replies(db, ctx.workspace_id)
    return ReplySyncResponse(synced=synced, message=f"Simulated {synced} replies (mock provider).")


@router.get("/export-csv")
def export_replies_csv(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    return PlainTextResponse(
        content=export_replies_to_csv(db, ctx.workspace_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=replies.csv"},
    )
