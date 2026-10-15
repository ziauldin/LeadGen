from __future__ import annotations

import logging
import smtplib
from collections import deque
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TransactionalEmail:
    to: str
    subject: str
    text: str
    tags: dict[str, str] = field(default_factory=dict)


class TransactionalMailer(Protocol):
    def send(self, email: TransactionalEmail) -> None: ...


# Last emails sent by the console mailer. Used by tests and the e2e test-mail endpoint.
OUTBOX: deque[TransactionalEmail] = deque(maxlen=200)


class ConsoleMailer:
    """Development/test mailer: logs the email and keeps it in memory."""

    def send(self, email: TransactionalEmail) -> None:
        OUTBOX.append(email)
        logger.info("Platform email (console) to=%s subject=%s", email.to, email.subject)


class ResendMailer:
    def __init__(self, api_key: str, from_address: str) -> None:
        self.api_key = api_key
        self.from_address = from_address

    def send(self, email: TransactionalEmail) -> None:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.from_address,
                "to": [email.to],
                "subject": email.subject,
                "text": email.text,
                "tags": [{"name": k, "value": v} for k, v in email.tags.items()],
            },
            timeout=20.0,
        )
        response.raise_for_status()


class SmtpMailer:
    def __init__(self, host: str, port: int, username: str, password: str, from_address: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address

    def send(self, email: TransactionalEmail) -> None:
        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.text)
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)


def get_platform_mailer() -> TransactionalMailer:
    provider = settings.platform_email_provider.lower()
    if provider == "resend" and settings.platform_email_api_key:
        return ResendMailer(settings.platform_email_api_key, settings.platform_email_from)
    if provider == "smtp" and settings.platform_smtp_host:
        return SmtpMailer(
            settings.platform_smtp_host,
            settings.platform_smtp_port,
            settings.platform_smtp_username,
            settings.platform_smtp_password,
            settings.platform_email_from,
        )
    return ConsoleMailer()
