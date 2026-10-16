from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session
from app.services.billing.stripe_billing import enforce_dunning, expire_trials


@celery_app.task(name="billing.daily", ignore_result=True)
def billing_housekeeping() -> dict[str, int]:
    """Hourly (cheap, idempotent): end expired trials and pause long-overdue accounts."""
    db = SessionLocal()
    try:
        with system_session(db):
            return {"trials_ended": expire_trials(db), "sending_paused": enforce_dunning(db)}
    finally:
        db.close()
