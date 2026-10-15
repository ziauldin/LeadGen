from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.inbound.imap_poller import poll_all_inboxes
from app.services.inbound.ingest import process_webhook_event, retry_failed_events


@celery_app.task(name="webhooks.process")
def process_webhook_task(event_id: int) -> str:
    db = SessionLocal()
    try:
        return process_webhook_event(db, event_id)
    finally:
        db.close()


@celery_app.task(name="webhooks.retry_failed")
def retry_failed_webhooks() -> int:
    db = SessionLocal()
    try:
        return retry_failed_events(db)
    finally:
        db.close()


@celery_app.task(name="inbox.poll")
def poll_inboxes() -> int:
    if not settings.feature_imap:
        return 0
    db = SessionLocal()
    try:
        return poll_all_inboxes(db)
    finally:
        db.close()
