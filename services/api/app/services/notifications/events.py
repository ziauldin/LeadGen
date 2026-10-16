"""Product events that notify people. Each is best effort: it never breaks the caller."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Concatenate

from sqlalchemy.orm import Session

from app.models.enums import ReplyClassification
from app.services.notifications.service import notify

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.lead import Lead
    from app.models.privacy import DataRequest
    from app.models.reply import Reply
    from app.models.user import User
    from app.models.workspace import Workspace

logger = logging.getLogger(__name__)


def _safe[**P](
    fn: Callable[Concatenate[Session, P], None],
) -> Callable[Concatenate[Session, P], None]:
    def wrapper(db: Session, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            with db.begin_nested():
                fn(db, *args, **kwargs)
        except Exception:
            logger.exception("Notification %s failed", fn.__name__)

    return wrapper


@_safe
def reply_received(db: Session, reply: Reply, lead: Lead | None) -> None:
    if str(reply.classification) != ReplyClassification.POSITIVE or reply.is_auto_reply:
        return
    who = lead.full_name if lead else reply.from_email
    notify(
        db,
        reply.workspace_id,
        "positive_reply",
        f"{who} replied with interest",
        body=(reply.body or "")[:280],
        link=f"/replies?reply={reply.id}",
    )


@_safe
def campaign_paused(db: Session, campaign: Campaign) -> None:
    notify(
        db,
        campaign.workspace_id,
        "campaign_paused",
        f'Campaign "{campaign.name}" was paused',
        body=campaign.auto_paused_reason,
        link=f"/campaigns/{campaign.id}",
    )


@_safe
def payment_failed(db: Session, workspace: Workspace) -> None:
    notify(
        db,
        workspace.id,
        "payment_failed",
        f"Payment failed for {workspace.name}",
        body="Update your payment method to keep sending.",
        link="/settings/usage",
    )


@_safe
def member_joined(db: Session, workspace_id: int, user: User) -> None:
    notify(
        db,
        workspace_id,
        "member_joined",
        f"{user.name} joined the workspace",
        link="/settings/members",
    )


@_safe
def data_request_done(db: Session, request: DataRequest) -> None:
    labels = {"export": "Data export", "erase": "Erasure", "workspace_export": "Workspace export"}
    notify(
        db,
        request.workspace_id,
        "data_request_done",
        f"{labels.get(request.kind, 'Data request')} finished",
        link="/settings/privacy",
        user_ids=[request.requested_by_id] if request.requested_by_id else None,
    )
