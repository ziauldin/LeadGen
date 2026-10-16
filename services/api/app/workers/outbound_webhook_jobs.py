from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.developer import WebhookDelivery
from app.services.developer.webhooks import attempt_delivery, due_deliveries


@celery_app.task(name="outbound_webhooks.deliver", acks_late=True)
def deliver_outbound_webhook(delivery_id: int) -> str:
    db = SessionLocal()
    try:
        with system_session(db):  # find which workspace the delivery belongs to
            delivery = db.get(WebhookDelivery, delivery_id)
        if delivery is None:
            return "missing"
        with workspace_scope(db, delivery.workspace_id):
            return attempt_delivery(db, delivery_id)
    finally:
        db.close()


@celery_app.task(name="outbound_webhooks.retry_due", ignore_result=True)
def retry_due_webhooks() -> int:
    """Every minute: queue deliveries whose next attempt is due (retries and missed sends)."""
    db = SessionLocal()
    try:
        with system_session(db):
            ids = due_deliveries(db)
    finally:
        db.close()
    for delivery_id in ids:
        deliver_outbound_webhook.delay(delivery_id)
    return len(ids)
