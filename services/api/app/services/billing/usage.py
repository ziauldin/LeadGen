"""Usage counters and quota checks.

Counters are keyed by ``(workspace, metric, period)`` and incremented with a conditional
UPDATE (falling back to INSERT), which is safe under concurrency on PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import QuotaExceededError
from app.models.campaign import Campaign
from app.models.workspace import UsageCounter, Workspace, WorkspaceInvitation, WorkspaceMember
from app.services.billing import credits
from app.services.billing.plans import METRIC_PERIOD, limits_for


def period_key(metric: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if METRIC_PERIOD.get(metric) == "day":
        return now.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m")


def current_usage(
    db: Session,
    workspace_id: int,
    metric: str,
    *,
    now: datetime | None = None,
) -> int:
    return (
        db.scalar(
            select(UsageCounter.count).where(
                UsageCounter.workspace_id == workspace_id,
                UsageCounter.metric == metric,
                UsageCounter.period_key == period_key(metric, now),
            ),
        )
        or 0
    )


def remaining(db: Session, workspace: Workspace, metric: str) -> int:
    """Units left this period: the plan's allowance plus whatever prepaid credits cover."""
    limit = getattr(limits_for(workspace), metric)
    left = max(0, limit - current_usage(db, workspace.id, metric))
    if metric in credits.CREDIT_UNITS:
        left += max(0, credits.balance(db, workspace.id)) * credits.CREDIT_UNITS[metric]
    return left


def _overflow(used: int, amount: int, limit: int) -> int:
    """How much of ``amount`` falls beyond the plan's allowance."""
    return max(0, used + amount - max(limit, used))


def check_quota(db: Session, workspace: Workspace, metric: str, amount: int = 1) -> None:
    limit = getattr(limits_for(workspace), metric)
    used = current_usage(db, workspace.id, metric)
    if used + amount <= limit:
        return
    if metric in credits.CREDIT_UNITS:
        needed = credits.credits_for(metric, _overflow(used, amount, limit))
        if needed <= credits.balance(db, workspace.id):
            return
    raise QuotaExceededError(metric, limit, used)


def record_usage(db: Session, workspace_id: int, metric: str, amount: int = 1) -> None:
    """Add ``amount`` to the counter, taking credits for any part beyond the plan.

    Flushes, does not commit.
    """
    if amount <= 0:
        return
    if metric in credits.CREDIT_UNITS:
        workspace = db.get(Workspace, workspace_id)
        if workspace is not None:
            limit = getattr(limits_for(workspace), metric)
            overflow = _overflow(current_usage(db, workspace_id, metric), amount, limit)
            credits.charge(db, workspace_id, metric, credits.credits_for(metric, overflow))
    key = period_key(metric)
    condition = (
        (UsageCounter.workspace_id == workspace_id)
        & (UsageCounter.metric == metric)
        & (UsageCounter.period_key == key)
    )
    result = db.execute(
        update(UsageCounter)
        .where(condition)
        .values(count=UsageCounter.count + amount)
        .execution_options(synchronize_session=False),
    )
    if result.rowcount:  # type: ignore[attr-defined]
        return
    try:
        with db.begin_nested():
            db.add(
                UsageCounter(
                    workspace_id=workspace_id, metric=metric, period_key=key, count=amount
                ),
            )
    except IntegrityError:
        db.execute(
            update(UsageCounter)
            .where(condition)
            .values(count=UsageCounter.count + amount)
            .execution_options(synchronize_session=False),
        )


def check_seat_available(db: Session, workspace: Workspace) -> None:
    members = (
        db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace.id,
            ),
        )
        or 0
    )
    pending = (
        db.scalar(
            select(func.count(WorkspaceInvitation.id)).where(
                WorkspaceInvitation.workspace_id == workspace.id,
                WorkspaceInvitation.accepted_at.is_(None),
                WorkspaceInvitation.revoked_at.is_(None),
                WorkspaceInvitation.expires_at > datetime.now(UTC),
            ),
        )
        or 0
    )
    seats = limits_for(workspace).seats
    if members + pending >= seats:
        raise QuotaExceededError("seats", seats, members + pending)


def check_campaign_limit(db: Session, workspace: Workspace) -> None:
    count = (
        db.scalar(select(func.count(Campaign.id)).where(Campaign.workspace_id == workspace.id)) or 0
    )
    limit = limits_for(workspace).max_campaigns
    if count >= limit:
        raise QuotaExceededError("max_campaigns", limit, count)


MAILBOX_PROVIDER_NAMES = ("gmail", "outlook")


def connected_mailboxes(db: Session, workspace_id: int) -> int:
    from app.models.enums import ProviderType
    from app.models.provider_credential import ProviderCredential

    return (
        db.scalar(
            select(func.count(ProviderCredential.id)).where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider_type == ProviderType.EMAIL,
                ProviderCredential.provider_name.in_(MAILBOX_PROVIDER_NAMES),
            )
        )
        or 0
    )


def check_mailbox_limit(db: Session, workspace: Workspace) -> None:
    """Raise when connecting one more mailbox would go over the plan."""
    used = connected_mailboxes(db, workspace.id)
    limit = limits_for(workspace).max_mailboxes
    if used >= limit:
        raise QuotaExceededError("max_mailboxes", limit, used)
