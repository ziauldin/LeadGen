"""Notify workspace members in the app, by email and in Slack, respecting their preferences."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tenancy import workspace_scope
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.models.workspace import WorkspaceMember, WorkspaceRole, WorkspaceSettings
from app.services.platform_email.dispatch import send_platform_email
from app.services.platform_email.mailer import TransactionalEmail

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Kind:
    label: str
    in_app: bool  # default for the in-app bell (None = not offered)
    email: bool  # default for email
    roles: tuple[str, ...] = ("owner", "admin", "member")  # who receives it


KINDS: dict[str, Kind] = {
    "positive_reply": Kind("Someone replies with interest", True, True),
    "campaign_paused": Kind("A campaign is paused automatically", True, True, ("owner", "admin")),
    "payment_failed": Kind("A payment fails", True, True, ("owner",)),
    "trial_ending": Kind("The free trial is about to end", True, True, ("owner",)),
    "member_joined": Kind("Someone joins the workspace", True, False, ("owner", "admin")),
    "data_request_done": Kind("A data request is ready", True, False, ("owner", "admin")),
    "task_due": Kind("A task assigned to me is due", True, True),
    "weekly_digest": Kind("Weekly summary", False, True, ("owner", "admin")),
}
SLACK_KINDS = ("positive_reply", "campaign_paused", "payment_failed", "member_joined")


def preferences(db: Session, user_id: int) -> dict[str, dict[str, bool]]:
    stored = (
        db.scalar(
            select(NotificationPreference.settings).where(NotificationPreference.user_id == user_id)
        )
        or {}
    )
    result: dict[str, dict[str, bool]] = {}
    for key, kind in KINDS.items():
        saved = stored.get(key) or {}
        result[key] = {
            "in_app": bool(saved.get("in_app", kind.in_app)),
            "email": bool(saved.get("email", kind.email)),
        }
    return result


def save_preferences(
    db: Session, user_id: int, values: dict[str, dict[str, bool]]
) -> dict[str, dict[str, bool]]:
    clean = {
        key: {
            channel: bool(flag)
            for channel, flag in channels.items()
            if channel in ("in_app", "email")
        }
        for key, channels in values.items()
        if key in KINDS
    }
    row = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if row is None:
        row = NotificationPreference(user_id=user_id, settings=clean)
        db.add(row)
    else:
        row.settings = {**(row.settings or {}), **clean}
    db.commit()
    return preferences(db, user_id)


def _recipients(
    db: Session, workspace_id: int, roles: tuple[str, ...], user_ids: list[int] | None
) -> list[User]:
    query = (
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role.in_([WorkspaceRole(r) for r in roles]),
            User.is_active.is_(True),
        )
    )
    if user_ids is not None:
        query = query.where(User.id.in_(user_ids))
    return list(db.scalars(query).all())


def notify(
    db: Session,
    workspace_id: int,
    kind: str,
    title: str,
    *,
    body: str | None = None,
    link: str | None = None,
    user_ids: list[int] | None = None,
    email_text: str | None = None,
) -> int:
    """Create notifications (and emails) for the members who want this kind. Returns how many."""
    # Callers aren't always scoped to this workspace (e.g. someone accepting an invitation is
    # still in their own); row-level security needs the session scoped to where we write.
    if db.info.get("tenant_bypass") or db.info.get("workspace_id") == workspace_id:
        return _notify(
            db,
            workspace_id,
            kind,
            title,
            body=body,
            link=link,
            user_ids=user_ids,
            email_text=email_text,
        )
    with workspace_scope(db, workspace_id):
        return _notify(
            db,
            workspace_id,
            kind,
            title,
            body=body,
            link=link,
            user_ids=user_ids,
            email_text=email_text,
        )


def _notify(
    db: Session,
    workspace_id: int,
    kind: str,
    title: str,
    *,
    body: str | None,
    link: str | None,
    user_ids: list[int] | None,
    email_text: str | None,
) -> int:
    spec = KINDS[kind]
    sent = 0
    for user in _recipients(db, workspace_id, spec.roles, user_ids):
        prefs = preferences(db, user.id)[kind]
        if prefs["in_app"]:
            db.add(
                Notification(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    kind=kind,
                    title=title,
                    body=body,
                    link=link,
                )
            )
            sent += 1
        if prefs["email"]:
            url = f"{settings.frontend_url.rstrip('/')}{link}" if link else settings.frontend_url
            send_platform_email(
                TransactionalEmail(
                    to=user.email,
                    subject=title,
                    text=(
                        f"Hi {user.name},\n\n{email_text or body or title}\n\n{url}\n\n"
                        "You can change which emails you get in Settings, under Notifications.\n"
                    ),
                    tags={"kind": f"notify:{kind}"},
                )
            )
    db.flush()  # write while the session is scoped to this workspace
    if kind in SLACK_KINDS:
        _post_to_slack(db, workspace_id, kind, title, body, link)
    return sent


def _post_to_slack(
    db: Session, workspace_id: int, kind: str, title: str, body: str | None, link: str | None
) -> None:
    ws_settings = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )
    if ws_settings is None or not ws_settings.slack_webhook_encrypted:
        return
    if kind not in (ws_settings.slack_events or []):
        return
    from app.workers.notification_jobs import post_to_slack

    url = f"{settings.frontend_url.rstrip('/')}{link}" if link else None
    text = (
        f"*{title}*"
        + (f"\n{body}" if body else "")
        + (f"\n<{url}|Open in LeadsGen>" if url else "")
    )
    try:
        post_to_slack.delay(workspace_id, text)
    except Exception:  # Slack is best effort
        logger.exception("Could not queue Slack notification")


def notification_payload(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read_at is not None,
        "created_at": n.created_at,
    }
