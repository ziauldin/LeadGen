import logging
import uuid

from app.services.sending.base import EmailSender, SendResult

logger = logging.getLogger(__name__)


class MockEmailSender(EmailSender):
    provider_name = "mock"

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        message_id = f"mock-{uuid.uuid4().hex[:16]}"
        logger.info(
            "Mock email sent to=%s subject=%s message_id=%s",
            recipient_email,
            subject,
            message_id,
        )
        return SendResult(success=True, provider_message_id=message_id)
