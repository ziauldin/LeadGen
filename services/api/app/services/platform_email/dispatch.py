from __future__ import annotations

import logging
from dataclasses import asdict

from app.core.config import settings
from app.services.platform_email.mailer import (
    ConsoleMailer,
    TransactionalEmail,
    get_platform_mailer,
)

logger = logging.getLogger(__name__)


def send_platform_email(email: TransactionalEmail) -> None:
    """Send now for the console mailer, otherwise queue a Celery task with retries.

    If the queue is unavailable we fall back to sending inline, so a Redis outage never
    blocks password resets or sign-up verification.
    """
    mailer = get_platform_mailer()
    if isinstance(mailer, ConsoleMailer) or settings.celery_task_always_eager:
        _send_inline(email)
        return

    from app.workers.platform_email_jobs import send_platform_email_task

    try:
        send_platform_email_task.delay(asdict(email))
    except Exception as exc:
        logger.warning("Queueing platform email failed (%s); sending inline", exc)
        _send_inline(email)


def _send_inline(email: TransactionalEmail) -> None:
    try:
        get_platform_mailer().send(email)
    except Exception:
        logger.exception("Platform email to %s failed", email.to)
