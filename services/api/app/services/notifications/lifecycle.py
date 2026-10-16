"""Lifecycle emails: welcome, verification reminder, trial ending and the weekly digest.

Each email is recorded in ``lifecycle_emails`` under a key, so it goes out at most once.
Run from beat inside a system (cross-tenant) session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.flags import feature_enabled
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, ReplyClassification
from app.models.lead import Lead
from app.models.notification import LifecycleEmail
from app.models.reply import Reply
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.services.analytics.service import weekly_report_lines
from app.services.notifications.service import notify, preferences
from app.services.platform_email.dispatch import send_platform_email
from app.services.platform_email.mailer import TransactionalEmail

SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)


def _now() -> datetime:
    return datetime.now(UTC)


def _claim(db: Session, user_id: int, key: str, workspace_id: int | None = None) -> bool:
    """Record that ``key`` is being sent to this user. False if it already was."""
    if db.scalar(
        select(LifecycleEmail.id).where(
            LifecycleEmail.user_id == user_id, LifecycleEmail.key == key
        )
    ):
        return False
    try:
        with db.begin_nested():
            db.add(LifecycleEmail(user_id=user_id, key=key, workspace_id=workspace_id))
    except IntegrityError:
        return False
    return True


def _app(path: str = "") -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}"


def send_welcome(db: Session, user: User) -> bool:
    if not _claim(db, user.id, "welcome"):
        return False
    send_platform_email(
        TransactionalEmail(
            to=user.email,
            subject=f"Welcome to {settings.app_name}",
            text=(
                f"Hi {user.name},\n\nThanks for confirming your email. Here's the quickest way to your first campaign:\n\n"
                "1. Add your sender details and business address\n"
                "2. Connect your sending account (Resend, SendGrid, Mailgun or SMTP)\n"
                "3. Check SPF, DKIM and DMARC under Deliverability\n"
                "4. Find or import leads, then build a campaign\n\n"
                f"The setup guide walks you through it: {_app('/onboarding')}\n\n"
                f"Questions? Just reply, or visit {_app('/help')}.\n"
            ),
            tags={"kind": "lifecycle:welcome"},
        )
    )
    db.commit()
    return True


def send_verification_reminders(db: Session) -> int:
    """One reminder for accounts still unverified 24 hours after signing up (within a week)."""
    from app.services.auth.service import send_verification

    now = _now()
    sent = 0
    for user in db.scalars(
        select(User).where(
            User.email_verified_at.is_(None),
            User.is_active.is_(True),
            User.created_at <= now - timedelta(hours=24),
            User.created_at >= now - timedelta(days=7),
        )
    ).all():
        if _claim(db, user.id, "verify_reminder"):
            db.commit()
            send_verification(db, user)
            sent += 1
    return sent


def notify_trials_ending(db: Session, *, days: int = 3) -> int:
    now = _now()
    count = 0
    for workspace in db.scalars(
        select(Workspace).where(
            Workspace.trial_ends_at.is_not(None),
            Workspace.trial_ends_at > now,
            Workspace.trial_ends_at <= now + timedelta(days=days),
        )
    ).all():
        ends = workspace.trial_ends_at
        assert ends is not None  # noqa: S101
        key = f"trial_ending:{workspace.id}:{ends.date().isoformat()}"
        owners = db.scalars(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        ).all()
        claimed = [uid for uid in owners if _claim(db, uid, key, workspace.id)]
        if claimed:
            notify(
                db,
                workspace.id,
                "trial_ending",
                f"Your {workspace.name} trial ends on {ends.strftime('%d %B')}",
                body="Choose a plan to keep your current limits. Nothing is deleted if you don't.",
                link="/settings/usage",
                user_ids=claimed,
            )
            count += 1
    db.commit()
    return count


def weekly_digest(db: Session, *, now: datetime | None = None) -> int:
    """Monday summary for owners and admins of workspaces with activity in the last 7 days."""
    now = now or _now()
    since = now - timedelta(days=7)
    year, week, _ = now.isocalendar()
    key = f"digest:{year}-W{week:02d}"
    sent_by_ws = dict(
        db.execute(
            select(EmailMessage.workspace_id, func.count(EmailMessage.id))
            .where(EmailMessage.status.in_(SENT_LIKE), EmailMessage.sent_at >= since)
            .group_by(EmailMessage.workspace_id)
        ).all()
    )
    replies_by_ws = dict(
        db.execute(
            select(Reply.workspace_id, func.count(Reply.id))
            .where(Reply.received_at >= since)
            .group_by(Reply.workspace_id)
        ).all()
    )
    positive_by_ws = dict(
        db.execute(
            select(Reply.workspace_id, func.count(Reply.id))
            .where(Reply.received_at >= since, Reply.classification == ReplyClassification.POSITIVE)
            .group_by(Reply.workspace_id)
        ).all()
    )
    leads_by_ws = dict(
        db.execute(
            select(Lead.workspace_id, func.count(Lead.id))
            .where(Lead.created_at >= since)
            .group_by(Lead.workspace_id)
        ).all()
    )
    active = set(sent_by_ws) | set(replies_by_ws) | set(leads_by_ws)
    emails = 0
    for workspace in db.scalars(
        select(Workspace).where(Workspace.id.in_(active), Workspace.deleted_at.is_(None))
    ).all():
        stats = (
            f"Emails sent: {sent_by_ws.get(workspace.id, 0)}\n"
            f"Replies: {replies_by_ws.get(workspace.id, 0)} ({positive_by_ws.get(workspace.id, 0)} interested)\n"
            f"New leads: {leads_by_ws.get(workspace.id, 0)}\n"
        )
        analytics_link = ""
        if feature_enabled("analytics_v2", workspace):
            extra = weekly_report_lines(db, workspace.id)
            if extra:
                stats += "\n".join(extra) + "\n"
            analytics_link = f"See the full breakdown: {_app('/analytics')}\n"
        for _member, user in db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
                User.is_active.is_(True),
            )
        ).all():
            if not preferences(db, user.id)["weekly_digest"]["email"]:
                continue
            if not _claim(db, user.id, f"{key}:{workspace.id}", workspace.id):
                continue
            send_platform_email(
                TransactionalEmail(
                    to=user.email,
                    subject=f"Your week in {workspace.name}",
                    text=(
                        f"Hi {user.name},\n\nHere's what happened in {workspace.name} over the last 7 days:\n\n{stats}\n"
                        f"Open your dashboard: {_app('/dashboard')}\n"
                        f"{analytics_link}\n"
                        "Turn this email off in Settings, under Notifications.\n"
                    ),
                    tags={"kind": "lifecycle:digest"},
                )
            )
            emails += 1
    db.commit()
    return emails
