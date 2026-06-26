import smtplib
from email.message import EmailMessage as SmtpEmailMessage

import httpx

from app.services.sending.base import EmailSender, SendResult


class SmtpEmailSender(EmailSender):
    provider_name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str | None = None,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        message = SmtpEmailMessage()
        sender = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
        message["From"] = sender
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(message)
            return SendResult(success=True, provider_message_id=f"smtp-{recipient_email}")
        except Exception as exc:  # noqa: BLE001
            return SendResult(success=False, error=str(exc))


class ResendEmailSender(EmailSender):
    provider_name = "resend"

    def __init__(self, api_key: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        payload = {
            "from": f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email,
            "to": [recipient_email],
            "subject": subject,
            "text": body,
        }
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
            message_id = response.json().get("id", f"resend-{recipient_email}")
            return SendResult(success=True, provider_message_id=str(message_id))
        except Exception as exc:  # noqa: BLE001
            return SendResult(success=False, error=str(exc))


class SendGridEmailSender(EmailSender):
    provider_name = "sendgrid"

    def __init__(self, api_key: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        payload = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {
                "email": self.from_email,
                **({"name": self.from_name} if self.from_name else {}),
            },
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
            return SendResult(success=True, provider_message_id=response.headers.get("X-Message-Id", "sendgrid"))
        except Exception as exc:  # noqa: BLE001
            return SendResult(success=False, error=str(exc))


class MailgunEmailSender(EmailSender):
    provider_name = "mailgun"

    def __init__(self, api_key: str, domain: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.domain = domain
        self.from_email = from_email
        self.from_name = from_name

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        sender = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
        try:
            response = httpx.post(
                f"https://api.mailgun.net/v3/{self.domain}/messages",
                auth=("api", self.api_key),
                data={
                    "from": sender,
                    "to": recipient_email,
                    "subject": subject,
                    "text": body,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            message_id = response.json().get("id", f"mailgun-{recipient_email}")
            return SendResult(success=True, provider_message_id=str(message_id))
        except Exception as exc:  # noqa: BLE001
            return SendResult(success=False, error=str(exc))
