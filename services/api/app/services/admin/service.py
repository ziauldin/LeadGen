"""Platform-wide queries for the admin back office. Run inside a system (cross-tenant) session."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.flags import FLAGS
from app.models.developer import WebhookDelivery
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, ProviderCredentialStatus
from app.models.lead import Lead
from app.models.privacy import DataRequest
from app.models.provider_credential import ProviderCredential
from app.models.reply import Reply
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.services.billing.plans import PLAN_FEATURES, PLANS

SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)
# Thresholds for the abuse queue (7-day window, minimum volume to avoid noise).
ABUSE_MIN_SENDS = 20
ABUSE_BOUNCE_RATE = 0.05
ABUSE_COMPLAINT_RATE = 0.003
DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "10minutemail.com",
        "tempmail.com",
        "temp-mail.org",
        "yopmail.com",
        "trashmail.com",
        "sharklasers.com",
        "getnada.com",
        "dispostable.com",
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def sending_stats(
    db: Session, since: datetime, workspace_ids: list[int] | None = None
) -> dict[int, dict[str, int]]:
    """Sent / bounced / complained counts per workspace since ``since``."""
    query = (
        select(
            EmailMessage.workspace_id,
            func.count(EmailMessage.id),
            func.sum(case((EmailMessage.status == EmailMessageStatus.BOUNCED, 1), else_=0)),
            func.sum(case((EmailMessage.status == EmailMessageStatus.COMPLAINED, 1), else_=0)),
        )
        .where(EmailMessage.status.in_(SENT_LIKE), EmailMessage.sent_at >= since)
        .group_by(EmailMessage.workspace_id)
    )
    if workspace_ids is not None:
        query = query.where(EmailMessage.workspace_id.in_(workspace_ids))
    return {
        ws: {
            "sent": int(sent or 0),
            "bounced": int(bounced or 0),
            "complained": int(complained or 0),
        }
        for ws, sent, bounced, complained in db.execute(query).all()
    }


def _rate(part: int, total: int) -> float:
    return round(part / total, 4) if total else 0.0


def workspace_rows(db: Session, workspaces: list[Workspace]) -> list[dict[str, Any]]:
    ids = [w.id for w in workspaces]
    if not ids:
        return []
    members = dict(
        db.execute(
            select(WorkspaceMember.workspace_id, func.count(WorkspaceMember.id))
            .where(WorkspaceMember.workspace_id.in_(ids))
            .group_by(WorkspaceMember.workspace_id)
        ).all()
    )
    leads = dict(
        db.execute(
            select(Lead.workspace_id, func.count(Lead.id))
            .where(Lead.workspace_id.in_(ids))
            .group_by(Lead.workspace_id)
        ).all()
    )
    owners = dict(
        db.execute(
            select(WorkspaceMember.workspace_id, func.min(User.email))
            .join(User, User.id == WorkspaceMember.user_id)
            .where(
                WorkspaceMember.workspace_id.in_(ids), WorkspaceMember.role == WorkspaceRole.OWNER
            )
            .group_by(WorkspaceMember.workspace_id)
        ).all()
    )
    stats = sending_stats(db, _now() - timedelta(days=30), ids)
    rows = []
    for workspace in workspaces:
        s = stats.get(workspace.id, {"sent": 0, "bounced": 0, "complained": 0})
        rows.append(
            {
                "id": workspace.id,
                "name": workspace.name,
                "plan": workspace.plan,
                "owner_email": owners.get(workspace.id),
                "members": int(members.get(workspace.id, 0)),
                "leads": int(leads.get(workspace.id, 0)),
                "sent_30d": s["sent"],
                "bounce_rate_30d": _rate(s["bounced"], s["sent"]),
                "complaint_rate_30d": _rate(s["complained"], s["sent"]),
                "sending_suspended_at": workspace.sending_suspended_at,
                "sending_suspended_reason": workspace.sending_suspended_reason,
                "deleted_at": workspace.deleted_at,
                "created_at": workspace.created_at,
            }
        )
    return rows


def overview(db: Session) -> dict[str, Any]:
    now = _now()
    week = now - timedelta(days=7)
    day = now - timedelta(days=1)
    plans = dict(
        db.execute(
            select(Workspace.plan, func.count(Workspace.id))
            .where(Workspace.deleted_at.is_(None))
            .group_by(Workspace.plan)
        ).all()
    )
    stats_7d = sending_stats(db, week)
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "new_users_7d": db.scalar(select(func.count(User.id)).where(User.created_at >= week)) or 0,
        "workspaces": sum(plans.values()),
        "workspaces_by_plan": {k: int(v) for k, v in plans.items()},
        "active_workspaces_7d": len(stats_7d),
        "suspended_workspaces": db.scalar(
            select(func.count(Workspace.id)).where(Workspace.sending_suspended_at.is_not(None))
        )
        or 0,
        "emails_sent_24h": db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.status.in_(SENT_LIKE), EmailMessage.sent_at >= day
            )
        )
        or 0,
        "emails_sent_7d": sum(s["sent"] for s in stats_7d.values()),
        "replies_7d": db.scalar(select(func.count(Reply.id)).where(Reply.received_at >= week)) or 0,
    }


def abuse_queue(db: Session) -> dict[str, Any]:
    now = _now()
    stats = sending_stats(db, now - timedelta(days=7))
    flagged_ids = [
        ws
        for ws, s in stats.items()
        if s["sent"] >= ABUSE_MIN_SENDS
        and (
            s["bounced"] / s["sent"] >= ABUSE_BOUNCE_RATE
            or s["complained"] / s["sent"] >= ABUSE_COMPLAINT_RATE
        )
    ]
    workspaces = (
        db.scalars(select(Workspace).where(Workspace.id.in_(flagged_ids))).all()
        if flagged_ids
        else []
    )
    sending = []
    for workspace in workspaces:
        s = stats[workspace.id]
        reasons = []
        if s["bounced"] / s["sent"] >= ABUSE_BOUNCE_RATE:
            reasons.append(f"Bounce rate {s['bounced'] / s['sent']:.1%} over 7 days")
        if s["complained"] / s["sent"] >= ABUSE_COMPLAINT_RATE:
            reasons.append(f"Complaint rate {s['complained'] / s['sent']:.2%} over 7 days")
        sending.append(
            {
                "workspace_id": workspace.id,
                "name": workspace.name,
                "plan": workspace.plan,
                "sent_7d": s["sent"],
                "bounced_7d": s["bounced"],
                "complained_7d": s["complained"],
                "suspended": workspace.sending_suspended_at is not None,
                "reasons": reasons,
            }
        )

    signups = []
    for user in db.scalars(
        select(User)
        .where(User.created_at >= now - timedelta(days=14))
        .order_by(User.created_at.desc())
    ).all():
        reasons = []
        domain = user.email.rsplit("@", 1)[-1].lower()
        if domain in DISPOSABLE_DOMAINS:
            reasons.append("Disposable email domain")
        created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=UTC)
        if user.email_verified_at is None and created <= now - timedelta(days=3):
            reasons.append("Email not verified after 3 days")
        if reasons:
            signups.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "created_at": user.created_at,
                    "is_active": user.is_active,
                    "reasons": reasons,
                }
            )
    return {"sending": sending, "signups": signups}


def system_health(db: Session) -> dict[str, Any]:
    from app.services.health.checks import check_database, check_redis, check_worker_heartbeat

    day = _now() - timedelta(days=1)
    checks = {}
    for name, check in (
        ("database", lambda: check_database(db)),
        ("redis", check_redis),
        ("worker", check_worker_heartbeat),
    ):
        ok, detail = check()
        checks[name] = {"ok": ok, "detail": detail}
    return {
        "checks": checks,
        "failed_emails_24h": db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.status == EmailMessageStatus.FAILED, EmailMessage.updated_at >= day
            )
        )
        or 0,
        "queued_emails": db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.status.in_([EmailMessageStatus.QUEUED, EmailMessageStatus.SENDING])
            )
        )
        or 0,
        "provider_errors": db.scalar(
            select(func.count(ProviderCredential.id)).where(
                ProviderCredential.status == ProviderCredentialStatus.ERROR
            )
        )
        or 0,
        "webhooks_pending": db.scalar(
            select(func.count(WebhookDelivery.id)).where(WebhookDelivery.status == "pending")
        )
        or 0,
        "webhooks_failed_24h": db.scalar(
            select(func.count(WebhookDelivery.id)).where(
                WebhookDelivery.status == "failed", WebhookDelivery.created_at >= day
            )
        )
        or 0,
        "data_requests_open": db.scalar(
            select(func.count(DataRequest.id)).where(
                DataRequest.status.in_(["pending", "running", "failed"])
            )
        )
        or 0,
    }


def validate_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    limits = PLANS["free"].as_dict()
    features = PLAN_FEATURES["free"].as_dict()
    clean: dict[str, Any] = {}
    for key, value in overrides.items():
        if key == "features":
            if not isinstance(value, dict):
                raise ValidationFailedError("features must be an object")
            unknown = sorted(set(value) - set(features))
            if unknown:
                raise ValidationFailedError(f"Unknown plan features: {', '.join(unknown)}")
            clean["features"] = value
        elif key in limits:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValidationFailedError(f"{key} must be a whole number")
            clean[key] = value
        else:
            raise ValidationFailedError(f"Unknown plan limit: {key}")
    return clean


def validate_flags(flags: dict[str, Any]) -> dict[str, bool]:
    unknown = sorted(set(flags) - set(FLAGS))
    if unknown:
        raise ValidationFailedError(f"Unknown feature flags: {', '.join(unknown)}")
    return {key: bool(value) for key, value in flags.items() if value is not None}
