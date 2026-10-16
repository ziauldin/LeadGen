from app.core.celery_app import celery_app
from app.services.health.checks import record_heartbeat


@celery_app.task(name="ops.heartbeat", ignore_result=True)
def heartbeat() -> None:
    """Scheduled every minute by beat; /health/ready reports workers missing without it."""
    record_heartbeat()
