from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session
from app.services.crm.service import due_reminders


@celery_app.task(name="crm.task_reminders", ignore_result=True)
def task_reminders() -> int:
    """Every 5 minutes: tell people about tasks that just became due."""
    db = SessionLocal()
    try:
        with system_session(db):
            return due_reminders(db)
    finally:
        db.close()
