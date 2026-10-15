from typing import Any

from app.core.celery_app import celery_app
from app.services.platform_email.mailer import TransactionalEmail, get_platform_mailer


@celery_app.task(
    name="platform_email.send",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def send_platform_email_task(payload: dict[str, Any]) -> str:
    get_platform_mailer().send(TransactionalEmail(**payload))
    return "sent"
