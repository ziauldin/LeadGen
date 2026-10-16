from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.privacy import DataRequest
from app.services.privacy.service import apply_retention, process_request, purge_expired_exports


@celery_app.task(name="privacy.process_request", acks_late=True)
def process_data_request(request_id: int) -> str:
    db = SessionLocal()
    try:
        with system_session(db):  # find which workspace the request belongs to
            request = db.get(DataRequest, request_id)
        if request is None:
            return "missing"
        with workspace_scope(db, request.workspace_id):
            done = process_request(db, request_id)
            return done.status if done else "missing"
    finally:
        db.close()


@celery_app.task(name="privacy.apply_retention", ignore_result=True)
def apply_retention_task() -> dict[str, int]:
    """Daily: each workspace's retention rules, then expired export files."""
    db = SessionLocal()
    try:
        with system_session(db):
            totals = apply_retention(db)
            totals["exports"] = purge_expired_exports(db)
            return totals
    finally:
        db.close()
