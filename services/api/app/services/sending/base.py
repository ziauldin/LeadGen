from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class SendKind(StrEnum):
    OK = "ok"
    TRANSIENT = "transient"  # retry later (rate limit, 5xx, timeout, connection error)
    PERMANENT = "permanent"  # do not retry (rejected recipient, invalid request)


@dataclass
class OutboundEmail:
    to: str
    subject: str
    text: str
    html: str
    message_id: str  # RFC 5322 Message-ID, without angle brackets
    idempotency_key: str
    correlation_id: str  # our email_messages.id, sent as a provider tag/custom arg
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class SendResult:
    kind: SendKind
    provider_message_id: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.kind == SendKind.OK


class EmailSender(Protocol):
    provider_name: str
    from_email: str

    def send(self, email: OutboundEmail) -> SendResult: ...
