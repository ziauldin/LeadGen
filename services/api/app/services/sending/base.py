from dataclasses import dataclass


@dataclass
class SendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class EmailSender:
    provider_name: str

    def send(self, recipient_email: str, subject: str, body: str) -> SendResult:
        raise NotImplementedError
