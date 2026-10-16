from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, require_permission
from app.api.paging import PageParams, order_by, page_params
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.email_message import EmailMessage
from app.models.lead import Lead
from app.models.reply import Reply
from app.schemas.reply import (
    ReplyDetail,
    ReplyLinkRequest,
    ReplyListResponse,
    ReplyRead,
    ReplySyncResponse,
    ReplyUpdate,
    SentMessageSummary,
)
from app.services.inbound.processor import link_reply
from app.services.replies.export import export_replies_to_csv
from app.services.replies.service import update_reply
from app.services.replies.simulator import sync_mock_replies
from app.services.sending.provider_factory import is_mock_email_provider_active

router = APIRouter(prefix="/replies", tags=["replies"])


def _snippet(text: str, length: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= length else flat[: length - 1] + "…"


def _serialize_reply(reply: Reply, lead: Lead | None = None) -> ReplyRead:
    lead = lead or (reply.email_message.lead if reply.email_message else None)
    return ReplyRead(
        id=reply.id,
        email_message_id=reply.email_message_id,
        from_email=reply.from_email,
        subject=reply.subject,
        body=reply.body,
        snippet=_snippet(reply.body),
        classification=reply.classification,
        classified_by=reply.classified_by,
        classification_confidence=reply.classification_confidence,
        is_auto_reply=reply.is_auto_reply,
        match_method=reply.match_method,
        received_at=reply.received_at,
        lead_id=lead.id if lead else reply.lead_id,
        lead_name=lead.full_name if lead else None,
        campaign_id=reply.email_message.campaign_id if reply.email_message else None,
        notes=reply.notes,
    )


def _get_reply(db: Session, reply_id: int, ctx: WorkspaceContext) -> Reply:
    reply = db.scalar(
        select(Reply)
        .where(Reply.id == reply_id, Reply.workspace_id == ctx.workspace_id)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead)),
    )
    if reply is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found")
    return reply


@router.get("", response_model=ReplyListResponse)
def list_replies(
    classification: str | None = Query(default=None, max_length=50),
    campaign_id: int | None = None,
    search: str | None = Query(default=None, max_length=255),
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ReplyListResponse:
    skip, limit = page.skip, page.limit
    conditions = [Reply.workspace_id == ctx.workspace_id]
    if campaign_id is not None:
        conditions.append(Reply.email_message.has(EmailMessage.campaign_id == campaign_id))
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Reply.from_email.ilike(pattern),
                Reply.subject.ilike(pattern),
                Reply.body.ilike(pattern),
            ),
        )
    if classification == "unclassified":
        conditions.append(Reply.classification == "unknown")
    elif classification == "unmatched":
        conditions.append(Reply.email_message_id.is_(None))
    elif classification:
        conditions.append(Reply.classification == classification)

    total = db.scalar(select(func.count(Reply.id)).where(*conditions)) or 0
    replies = db.scalars(
        select(Reply)
        .where(*conditions)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead))
        .order_by(
            *order_by(
                page.sort,
                {"received_at": Reply.received_at, "classification": Reply.classification},
                [Reply.received_at.desc()],
                Reply.id,
            ),
        )
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
    _allowed: WorkspaceContext = Depends(require_permission(Permission.REPLIES_MANAGE)),
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
    _allowed: WorkspaceContext = Depends(require_permission(Permission.REPLIES_MANAGE)),
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
    _allowed: WorkspaceContext = Depends(require_permission(Permission.DATA_EXPORT)),
) -> PlainTextResponse:
    return PlainTextResponse(
        content=export_replies_to_csv(db, ctx.workspace_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=replies.csv"},
    )


@router.get("/{reply_id}", response_model=ReplyDetail)
def get_reply(
    reply_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ReplyDetail:
    reply = _get_reply(db, reply_id, ctx)
    lead = db.get(Lead, reply.lead_id) if reply.lead_id else None
    thread: list[SentMessageSummary] = []
    if reply.email_message is not None:
        conditions = [
            EmailMessage.workspace_id == ctx.workspace_id,
            EmailMessage.sent_at.is_not(None),
        ]
        if reply.email_message.enrollment_id:
            conditions.append(EmailMessage.enrollment_id == reply.email_message.enrollment_id)
        else:
            conditions.append(EmailMessage.id == reply.email_message.id)
        thread = [
            SentMessageSummary(
                id=m.id,
                subject=m.subject,
                body=m.body,
                sent_at=m.sent_at,
                step_number=m.step_number,
            )
            for m in db.scalars(
                select(EmailMessage).where(*conditions).order_by(EmailMessage.sent_at)
            ).all()
        ]
    base = _serialize_reply(reply, lead)
    return ReplyDetail(
        **base.model_dump(),
        raw_body=reply.raw_body,
        in_reply_to=reply.in_reply_to,
        thread=thread,
    )


@router.post("/{reply_id}/link", response_model=ReplyRead)
def link_reply_endpoint(
    reply_id: int,
    payload: ReplyLinkRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.REPLIES_MANAGE)),
) -> ReplyRead:
    reply = _get_reply(db, reply_id, ctx)
    message = db.scalar(
        select(EmailMessage).where(
            EmailMessage.id == payload.email_message_id,
            EmailMessage.workspace_id == ctx.workspace_id,
        ),
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email message not found")
    reply = link_reply(db, reply, message)
    return _serialize_reply(_get_reply(db, reply.id, ctx))
