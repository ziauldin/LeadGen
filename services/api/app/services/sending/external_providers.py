"""Real sending providers. Each returns OK / TRANSIENT / PERMANENT so the pipeline can retry."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr

import httpx

from app.services.sending.base import OutboundEmail, SendKind, SendResult

TIMEOUT = 20.0


def _classify_http(exc: Exception) -> SendResult:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = f"HTTP {status}"
        try:
            body = exc.response.json()
            message = body.get("message") or body.get("error") or ""
            if isinstance(message, str) and message:
                detail += f": {message[:200]}"
        except ValueError:
            pass
        if status == 429 or status >= 500:
            return SendResult(kind=SendKind.TRANSIENT, error=detail)
        return SendResult(kind=SendKind.PERMANENT, error=detail)
    return SendResult(kind=SendKind.TRANSIENT, error=f"{exc.__class__.__name__}")


def _sender(from_email: str, from_name: str | None) -> str:
    return formataddr((from_name, from_email)) if from_name else from_email


class SmtpEmailSender:
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

    def build_mime(self, email: OutboundEmail) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = _sender(self.from_email, self.from_name)
        mime["To"] = email.to
        mime["Subject"] = email.subject
        mime["Message-ID"] = f"<{email.message_id}>"
        for name, value in email.headers.items():
            mime[name] = value
        mime.set_content(email.text)
        mime.add_alternative(email.html, subtype="html")
        return mime

    def send(self, email: OutboundEmail) -> SendResult:
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(self.build_mime(email))
            # SMTP has no provider id: our own Message-ID is the stable identifier.
            return SendResult(kind=SendKind.OK, provider_message_id=email.message_id)
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [code for code, _ in exc.recipients.values()]
            kind = SendKind.TRANSIENT if all(400 <= c < 500 for c in codes) else SendKind.PERMANENT
            return SendResult(kind=kind, error=f"Recipient refused ({codes})")
        except smtplib.SMTPResponseException as exc:
            kind = SendKind.TRANSIENT if 400 <= exc.smtp_code < 500 else SendKind.PERMANENT
            return SendResult(kind=kind, error=f"SMTP {exc.smtp_code}")
        except (smtplib.SMTPException, OSError) as exc:
            return SendResult(kind=SendKind.TRANSIENT, error=exc.__class__.__name__)


class ResendEmailSender:
    provider_name = "resend"

    def __init__(self, api_key: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, email: OutboundEmail) -> SendResult:
        payload = {
            "from": _sender(self.from_email, self.from_name),
            "to": [email.to],
            "subject": email.subject,
            "text": email.text,
            "html": email.html,
            "headers": {"Message-ID": f"<{email.message_id}>", **email.headers},
            "tags": [{"name": "lg_msg_id", "value": email.correlation_id}],
        }
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": email.idempotency_key,
                },
                json=payload,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            return SendResult(kind=SendKind.OK, provider_message_id=str(response.json().get("id")))
        except (httpx.HTTPError, ValueError) as exc:
            return _classify_http(exc)


class SendGridEmailSender:
    provider_name = "sendgrid"

    def __init__(self, api_key: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, email: OutboundEmail) -> SendResult:
        payload = {
            "personalizations": [
                {"to": [{"email": email.to}], "custom_args": {"lg_msg_id": email.correlation_id}},
            ],
            "from": {
                "email": self.from_email,
                **({"name": self.from_name} if self.from_name else {}),
            },
            "subject": email.subject,
            "content": [
                {"type": "text/plain", "value": email.text},
                {"type": "text/html", "value": email.html},
            ],
            "headers": {"Message-ID": f"<{email.message_id}>", **email.headers},
        }
        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            return SendResult(
                kind=SendKind.OK,
                provider_message_id=response.headers.get("X-Message-Id") or email.message_id,
            )
        except httpx.HTTPError as exc:
            return _classify_http(exc)


class MailgunEmailSender:
    provider_name = "mailgun"

    def __init__(self, api_key: str, domain: str, from_email: str, from_name: str | None = None):
        self.api_key = api_key
        self.domain = domain
        self.from_email = from_email
        self.from_name = from_name

    def send(self, email: OutboundEmail) -> SendResult:
        data: dict[str, str] = {
            "from": _sender(self.from_email, self.from_name),
            "to": email.to,
            "subject": email.subject,
            "text": email.text,
            "html": email.html,
            "h:Message-Id": f"<{email.message_id}>",
            "v:lg_msg_id": email.correlation_id,
        }
        for name, value in email.headers.items():
            data[f"h:{name}"] = value
        try:
            response = httpx.post(
                f"https://api.mailgun.net/v3/{self.domain}/messages",
                auth=("api", self.api_key),
                data=data,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            provider_id = str(response.json().get("id") or email.message_id).strip("<>")
            return SendResult(kind=SendKind.OK, provider_message_id=provider_id)
        except (httpx.HTTPError, ValueError) as exc:
            return _classify_http(exc)
