"""The notification bell, notification preferences and the workspace Slack connection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.database import get_db
from app.core.errors import ValidationFailedError
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.notification import Notification
from app.models.workspace import WorkspaceSettings
from app.schemas.auth import MessageResponse
from app.services.notifications import slack
from app.services.notifications.service import (
    KINDS,
    SLACK_KINDS,
    notification_payload,
    preferences,
    save_preferences,
)
from app.services.workspaces.service import audit

router = APIRouter(tags=["notifications"])


class NotificationRead(BaseModel):
    id: int
    kind: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationRead]
    unread: int


class MarkRead(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=200)
    all: bool = False


class PreferenceKind(BaseModel):
    key: str
    label: str
    in_app: bool
    email: bool


class PreferencesUpdate(BaseModel):
    settings: dict[str, dict[str, bool]]


class SlackSettings(BaseModel):
    connected: bool
    events: list[str]
    available_events: list[PreferenceKind]


class SlackUpdate(BaseModel):
    webhook_url: str | None = Field(default=None, max_length=500)
    disconnect: bool = False
    events: list[str] | None = None


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> NotificationList:
    mine = [Notification.workspace_id == ctx.workspace_id, Notification.user_id == ctx.user_id]
    query = select(Notification).where(*mine)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows = db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    ).all()
    unread = (
        db.scalar(select(func.count(Notification.id)).where(*mine, Notification.read_at.is_(None)))
        or 0
    )
    return NotificationList(
        items=[NotificationRead(**notification_payload(n)) for n in rows], unread=unread
    )


@router.post("/notifications/read", response_model=MessageResponse)
def mark_read(
    payload: MarkRead,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> MessageResponse:
    conditions = [
        Notification.workspace_id == ctx.workspace_id,
        Notification.user_id == ctx.user_id,
        Notification.read_at.is_(None),
    ]
    if not payload.all:
        if not payload.ids:
            return MessageResponse(message="Nothing to mark")
        conditions.append(Notification.id.in_(payload.ids))
    db.execute(update(Notification).where(*conditions).values(read_at=datetime.now(UTC)))
    db.commit()
    return MessageResponse(message="Marked as read")


@router.get("/notifications/preferences", response_model=list[PreferenceKind])
def get_preferences(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> list[PreferenceKind]:
    prefs = preferences(db, ctx.user_id)
    return [PreferenceKind(key=key, label=kind.label, **prefs[key]) for key, kind in KINDS.items()]


@router.put("/notifications/preferences", response_model=list[PreferenceKind])
def update_preferences(
    payload: PreferencesUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PreferenceKind]:
    unknown = sorted(set(payload.settings) - KINDS.keys())
    if unknown:
        raise ValidationFailedError(f"Unknown notification types: {', '.join(unknown)}")
    prefs = save_preferences(db, ctx.user_id, payload.settings)
    return [PreferenceKind(key=key, label=kind.label, **prefs[key]) for key, kind in KINDS.items()]


def _settings_row(db: Session, ctx: WorkspaceContext) -> WorkspaceSettings:
    row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ctx.workspace_id)
    )
    if row is None:
        row = WorkspaceSettings(workspace_id=ctx.workspace_id)
        db.add(row)
        db.flush()
    return row


def _slack_read(row: WorkspaceSettings) -> SlackSettings:
    return SlackSettings(
        connected=bool(row.slack_webhook_encrypted),
        events=list(row.slack_events or []),
        available_events=[
            PreferenceKind(key=key, label=KINDS[key].label, in_app=False, email=False)
            for key in SLACK_KINDS
        ],
    )


@router.get("/workspaces/current/slack", response_model=SlackSettings)
def get_slack(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> SlackSettings:
    return _slack_read(_settings_row(db, ctx))


@router.put("/workspaces/current/slack", response_model=SlackSettings)
def update_slack(
    payload: SlackUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> SlackSettings:
    row = _settings_row(db, ctx)
    changes: dict[str, Any] = {}
    if payload.disconnect:
        slack.set_webhook(row, None)
        changes["connected"] = False
    elif payload.webhook_url:
        slack.set_webhook(row, payload.webhook_url)
        changes["connected"] = True
        if payload.events is None and not row.slack_events:
            row.slack_events = list(SLACK_KINDS)
    if payload.events is not None:
        unknown = sorted(set(payload.events) - set(SLACK_KINDS))
        if unknown:
            raise ValidationFailedError(f"Unknown Slack events: {', '.join(unknown)}")
        row.slack_events = sorted(set(payload.events))
        changes["events"] = row.slack_events
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "slack_settings_updated",
        "workspace",
        ctx.workspace_id,
        changes,
    )
    db.commit()
    return _slack_read(row)


@router.post("/workspaces/current/slack/test", response_model=MessageResponse)
def test_slack(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> MessageResponse:
    ok, error = slack.send(
        _settings_row(db, ctx), f"LeadsGen is connected to this channel for *{ctx.workspace.name}*."
    )
    if not ok:
        raise ValidationFailedError(error or "Slack didn't accept the message")
    return MessageResponse(message="Test message sent to Slack")
