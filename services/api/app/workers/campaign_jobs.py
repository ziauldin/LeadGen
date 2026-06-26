from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.sending.sender import process_active_campaigns


@celery_app.task(name="campaign.process_sends")
def process_campaign_sends() -> dict[str, int]:
    db = SessionLocal()
    try:
        return process_active_campaigns(db)
    finally:
        db.close()


@celery_app.task(name="campaign.send_message")
def send_campaign_message(email_message_id: int) -> dict[str, str]:
    from app.services.sending.sender import send_email_message

    db = SessionLocal()
    try:
        message = send_email_message(db, email_message_id)
        return {
            "status": message.status.value
            if hasattr(message.status, "value")
            else str(message.status),
            "email_message_id": str(email_message_id),
        }
    except ValueError as exc:
        return {"status": "failed", "email_message_id": str(email_message_id), "error": str(exc)}
    finally:
        db.close()
