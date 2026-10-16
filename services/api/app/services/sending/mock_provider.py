import logging
from collections import deque

from app.services.sending.base import OutboundEmail, SendKind, SendResult

logger = logging.getLogger(__name__)

# Recently "sent" mock emails, for tests and local debugging.
MOCK_OUTBOX: deque[OutboundEmail] = deque(maxlen=500)


class MockEmailSender:
    provider_name = "mock"
    from_email = "mock@leadsgen.local"

    def send(self, email: OutboundEmail) -> SendResult:
        MOCK_OUTBOX.append(email)
        logger.info("Mock email sent to=%s message_id=%s", email.to, email.message_id)
        return SendResult(kind=SendKind.OK, provider_message_id=f"mock-{email.message_id}")
