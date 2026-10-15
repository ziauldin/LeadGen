from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.tenancy import workspace_scope
from app.models.workspace import Workspace
from app.services.replies.sync import sync_mock_replies
from app.services.sending.provider_factory import is_mock_email_provider_active


@celery_app.task(name="replies.sync")
def sync_replies(workspace_id: int | None = None) -> dict[str, int | str]:
    """Development-only reply simulator. Never fabricates replies in production or for
    workspaces that send through a real provider."""
    if settings.is_production:
        return {"status": "skipped", "synced": 0}

    db = SessionLocal()
    try:
        workspace_ids = (
            [workspace_id]
            if workspace_id is not None
            else list(db.scalars(select(Workspace.id).where(Workspace.deleted_at.is_(None))).all())
        )
        total = 0
        for ws_id in workspace_ids:
            with workspace_scope(db, ws_id):
                if is_mock_email_provider_active(db, ws_id):
                    total += sync_mock_replies(db, ws_id)
        return {"status": "ok", "synced": total}
    finally:
        db.close()
