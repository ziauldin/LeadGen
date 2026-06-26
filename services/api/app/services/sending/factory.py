from app.core.config import settings
from app.services.sending.mock_provider import MockEmailSender
from app.services.sending.smtp_provider import SmtpEmailSender


def get_email_sender():
    provider_key = settings.email_provider.lower()
    if provider_key == "mock" or not settings.smtp_enabled:
        return MockEmailSender()
    if provider_key == "smtp":
        return SmtpEmailSender()
    raise NotImplementedError(
        f"Email provider '{settings.email_provider}' is not configured. Use 'mock' for local development.",
    )
