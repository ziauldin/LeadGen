from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.provider_credential import ProviderCredential
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


@celery_app.task(name="inbox.wake_snoozed", ignore_result=True)
def wake_snoozed_conversations() -> int:
    from app.services.inbox.service import wake_snoozed

    db = SessionLocal()
    try:
        with system_session(db):
            return wake_snoozed(db)
    finally:
        db.close()


@celery_app.task(name="inbox.poll")
def poll_inboxes() -> int:
    total = 0
    db = SessionLocal()
    try:
        if settings.feature_imap:
            total += poll_all_inboxes(db)
        total += sync_mailboxes(db)
    finally:
        db.close()
    return total


def sync_mailboxes(db: Session) -> int:
    """Gmail / Microsoft 365: pull new replies and pause unhealthy mailboxes."""
    from app.services.mailboxes.service import check_health, mailboxes_to_sync, sync_inbox

    with system_session(db):
        credentials = [(c.id, c.workspace_id) for c in mailboxes_to_sync(db)]
    processed = 0
    for credential_id, workspace_id in credentials:
        with workspace_scope(db, workspace_id):
            credential = db.get(ProviderCredential, credential_id)
            if credential is None:
                continue
            processed += sync_inbox(db, credential)
            check_health(db, credential)
            db.commit()
    return processed
