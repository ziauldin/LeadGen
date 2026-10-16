from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.workspace import WorkspaceSettings
from app.services.notifications import lifecycle, slack


@celery_app.task(name="notifications.slack", ignore_result=True)
def post_to_slack(workspace_id: int, text: str) -> bool:
    db = SessionLocal()
    try:
        with workspace_scope(db, workspace_id):
            row = db.scalar(
                select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
            )
            return row is not None and slack.send(row, text)[0]
    finally:
        db.close()


@celery_app.task(name="notifications.daily", ignore_result=True)
def lifecycle_daily() -> dict[str, int]:
    """Verification reminders and trial-ending notices (each sent once)."""
    db = SessionLocal()
    try:
        with system_session(db):
            return {
                "verify_reminders": lifecycle.send_verification_reminders(db),
                "trials_ending": lifecycle.notify_trials_ending(db),
            }
    finally:
        db.close()


@celery_app.task(name="notifications.weekly_digest", ignore_result=True)
def weekly_digest() -> int:
    db = SessionLocal()
    try:
        with system_session(db):
            return lifecycle.weekly_digest(db)
    finally:
        db.close()
