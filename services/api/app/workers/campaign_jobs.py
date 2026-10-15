from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session
from app.services.sending.sender import deliver_message, dispatch, reap_stuck_messages


@celery_app.task(name="sending.send_message", acks_late=True)
def send_message_task(email_message_id: int) -> str:
    db = SessionLocal()
    try:
        with system_session(db):
            return deliver_message(db, email_message_id)
    finally:
        db.close()


@celery_app.task(name="sending.dispatch")
def dispatch_due_messages() -> dict[str, int]:
    db = SessionLocal()
    try:
        return dispatch(db, enqueue=lambda message_id: send_message_task.delay(message_id))
    finally:
        db.close()


@celery_app.task(name="sending.reap")
def reap_stuck() -> dict[str, int]:
    db = SessionLocal()
    try:
        return reap_stuck_messages(db)
    finally:
        db.close()


# Old task name kept so a beat process from the previous release keeps working during deploys.
@celery_app.task(name="campaign.process_sends")
def process_campaign_sends() -> dict[str, int]:
    return dispatch_due_messages()
