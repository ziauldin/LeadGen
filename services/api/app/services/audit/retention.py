"""Delete audit entries older than each workspace's plan allows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.workspace import Workspace
from app.services.billing.plans import features_for

# Entries with no workspace (sign-ins, platform admin actions) are kept this long.
PLATFORM_RETENTION_DAYS = 730


def purge_audit_logs(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    removed = 0
    for workspace in db.scalars(select(Workspace)).all():
        cutoff = now - timedelta(days=features_for(workspace).audit_log_retention_days)
        result = db.execute(
            delete(AuditLog).where(
                AuditLog.workspace_id == workspace.id, AuditLog.created_at < cutoff
            )
        )
        removed += result.rowcount or 0  # type: ignore[attr-defined]
    result = db.execute(
        delete(AuditLog).where(
            AuditLog.workspace_id.is_(None),
            AuditLog.created_at < now - timedelta(days=PLATFORM_RETENTION_DAYS),
        )
    )
    removed += result.rowcount or 0  # type: ignore[attr-defined]
    db.commit()
    return removed
