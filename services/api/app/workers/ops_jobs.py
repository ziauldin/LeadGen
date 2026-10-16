from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session
from app.services.audit.retention import purge_audit_logs
from app.services.health.checks import record_heartbeat


@celery_app.task(name="ops.heartbeat", ignore_result=True)
def heartbeat() -> None:
    """Scheduled every minute by beat; /health/ready reports workers missing without it."""
    record_heartbeat()


@celery_app.task(name="ops.purge_audit_logs", ignore_result=True)
def purge_audit_logs_task() -> int:
    """Daily: drop audit entries past the workspace plan's retention window."""
    db = SessionLocal()
    try:
        with system_session(db):
            return purge_audit_logs(db)
    finally:
        db.close()
