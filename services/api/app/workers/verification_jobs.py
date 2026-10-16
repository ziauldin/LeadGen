from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import workspace_scope
from app.models.workspace import Workspace
from app.services.verification.service import pending_contacts, verify_contacts, verify_leads


@celery_app.task(name="verification.verify_leads")
def verify_leads_task(workspace_id: int, lead_ids: list[int], force: bool = False) -> int:
    db = SessionLocal()
    try:
        with workspace_scope(db, workspace_id):
            workspace = db.get(Workspace, workspace_id)
            return verify_leads(db, workspace, lead_ids, force=force).checked if workspace else 0
    finally:
        db.close()


@celery_app.task(name="verification.verify_pending")
def verify_pending_task(workspace_id: int) -> int:
    """Contacts never checked yet (new imports and enrollments)."""
    db = SessionLocal()
    try:
        with workspace_scope(db, workspace_id):
            workspace = db.get(Workspace, workspace_id)
            if workspace is None:
                return 0
            return verify_contacts(db, workspace, pending_contacts(db, workspace_id)).checked
    finally:
        db.close()
