import smtplib
from email.message import EmailMessage as SmtpEmailMessage

from app.core.config import settings
from app.services.sending.base import EmailSender, SendResult


class SmtpEmailSender(EmailSender):
    provider_name = "smtp"

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        if not settings.smtp_enabled:
            return SendResult(success=False, error="SMTP sending is disabled")

        message = SmtpEmailMessage()
        message["From"] = settings.smtp_from_email or settings.smtp_user
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
            return SendResult(success=True, provider_message_id=f"smtp-{recipient_email}")
        except Exception as exc:
            return SendResult(success=False, error=str(exc))
