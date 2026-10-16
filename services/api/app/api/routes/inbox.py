"""Unified inbox: one conversation per person, across every mailbox and campaign."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.database import get_db
from app.core.errors import ValidationFailedError
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.company import Company
from app.models.inbox import Conversation
from app.models.lead import Lead
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services.inbox import service as inbox

router = APIRouter(prefix="/inbox", tags=["inbox"])


class ConversationRow(BaseModel):
    id: int
    lead_id: int | None
    lead_name: str | None
    company_name: str | None
    contact_email: str
    subject: str | None
    status: str
    assignee_id: int | None
    assignee_name: str | None
    snoozed_until: datetime | None
    labels: list[str]
    unread: bool
    last_classification: str | None
    last_message_at: datetime | None


class ConversationPage(BaseModel):
    items: list[ConversationRow]
    total: int
    skip: int
    limit: int
    counts: dict[str, int]


class ThreadItemRead(BaseModel):
    kind: str
    id: int
    at: datetime
    subject: str | None
    body: str
    from_email: str | None
    to_email: str | None
    status: str | None
    classification: str | None
    campaign_id: int | None


class ConversationDetail(ConversationRow):
    messages: list[ThreadItemRead]
    can_reply: bool


class ConversationUpdate(BaseModel):
    status: Literal["open", "snoozed", "done"] | None = None
    snoozed_until: datetime | None = None
    assignee_id: int | None = None
    labels: list[str] | None = Field(default=None, max_length=10)
    unread: bool | None = None


class ReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


class SentReply(BaseModel):
    email_message_id: int


class Suggestion(BaseModel):
    body: str


def _rows(db: Session, conversations: list[Conversation]) -> list[ConversationRow]:
    lead_ids = {c.lead_id for c in conversations if c.lead_id}
    leads = (
        {
            lead.id: (lead.full_name, company)
            for lead, company in db.execute(
                select(Lead, Company.name)
                .join(Company, Company.id == Lead.company_id, isouter=True)
                .where(Lead.id.in_(lead_ids))
            ).all()
        }
        if lead_ids
        else {}
    )
    user_ids = {c.assignee_id for c in conversations if c.assignee_id}
    names = (
        dict(db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    return [
        ConversationRow(
            id=c.id,
            lead_id=c.lead_id,
            lead_name=leads.get(c.lead_id, (None, None))[0] if c.lead_id else None,
            company_name=leads.get(c.lead_id, (None, None))[1] if c.lead_id else None,
            contact_email=c.contact_email,
            subject=c.subject,
            status=c.status,
            assignee_id=c.assignee_id,
            assignee_name=names.get(c.assignee_id) if c.assignee_id else None,
            snoozed_until=c.snoozed_until,
            labels=list(c.labels or []),
            unread=c.unread,
            last_classification=c.last_classification,
            last_message_at=c.last_message_at,
        )
        for c in conversations
    ]


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    status: Literal["open", "snoozed", "done", "all"] = "open",
    assigned: Literal["me", "unassigned", "any"] = "any",
    label: str | None = Query(default=None, max_length=30),
    classification: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationPage:
    inbox.backfill(db, ctx.workspace_id)
    now = datetime.now(UTC)
    base = [Conversation.workspace_id == ctx.workspace_id]
    # Snoozes that have run out count as open again.
    open_now = or_(
        Conversation.status == "open",
        (Conversation.status == "snoozed") & (Conversation.snoozed_until <= now),
    )
    counts = {
        "open": db.scalar(select(func.count(Conversation.id)).where(*base, open_now)) or 0,
        "unread": db.scalar(
            select(func.count(Conversation.id)).where(
                *base, open_now, Conversation.unread.is_(True)
            )
        )
        or 0,
        "mine": db.scalar(
            select(func.count(Conversation.id)).where(
                *base, open_now, Conversation.assignee_id == ctx.user_id
            )
        )
        or 0,
    }
    conditions = list(base)
    if status == "open":
        conditions.append(open_now)
    elif status == "snoozed":
        conditions.extend([Conversation.status == "snoozed", Conversation.snoozed_until > now])
    elif status == "done":
        conditions.append(Conversation.status == "done")
    if assigned == "me":
        conditions.append(Conversation.assignee_id == ctx.user_id)
    elif assigned == "unassigned":
        conditions.append(Conversation.assignee_id.is_(None))
    if classification:
        conditions.append(Conversation.last_classification == classification)
    if search:
        pattern = f"%{search.strip()}%"
        lead_match = select(Lead.id).where(
            Lead.workspace_id == ctx.workspace_id, Lead.full_name.ilike(pattern)
        )
        conditions.append(
            or_(
                Conversation.contact_email.ilike(pattern),
                Conversation.subject.ilike(pattern),
                Conversation.lead_id.in_(lead_match),
            )
        )
    rows = list(
        db.scalars(
            select(Conversation)
            .where(*conditions)
            .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
        ).all()
    )
    if label:
        rows = [c for c in rows if label in (c.labels or [])]
    total = len(rows)
    return ConversationPage(
        items=_rows(db, rows[skip : skip + limit]),
        total=total,
        skip=skip,
        limit=limit,
        counts=counts,
    )


def _detail(db: Session, conversation: Conversation) -> ConversationDetail:
    row = _rows(db, [conversation])[0]
    messages = [ThreadItemRead(**item.__dict__) for item in inbox.thread(db, conversation)]
    return ConversationDetail(
        **row.model_dump(), messages=messages, can_reply=conversation.lead_id is not None
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    conversation = inbox.get(db, ctx.workspace_id, conversation_id)
    if conversation.unread:
        conversation.unread = False
        db.commit()
    return _detail(db, conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationDetail)
def patch_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.REPLIES_MANAGE)),
) -> ConversationDetail:
    conversation = inbox.get(db, ctx.workspace_id, conversation_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("assignee_id") is not None:
        member = db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == ctx.workspace_id,
                WorkspaceMember.user_id == changes["assignee_id"],
            )
        )
        if member is None:
            raise ValidationFailedError("Assign conversations to people in this workspace")
    inbox.update_conversation(db, conversation, actor_id=ctx.user_id, changes=changes)
    return _detail(db, conversation)


@router.post("/conversations/{conversation_id}/reply", response_model=SentReply)
def reply(
    conversation_id: int,
    payload: ReplyRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(
        require_permission(Permission.REPLIES_MANAGE, verified=True)
    ),
) -> SentReply:
    conversation = inbox.get(db, ctx.workspace_id, conversation_id)
    message = inbox.send_reply(db, ctx.workspace, ctx.user_id, conversation, payload.body)
    return SentReply(email_message_id=message.id)


@router.post("/conversations/{conversation_id}/suggest", response_model=Suggestion)
def suggest(
    conversation_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.REPLIES_MANAGE)),
) -> Suggestion:
    conversation = inbox.get(db, ctx.workspace_id, conversation_id)
    return Suggestion(body=inbox.suggest_reply(db, ctx.workspace, ctx.user_id, conversation))
