"""Email message lifecycle. Every status change goes through :func:`transition`."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus as S

ALLOWED: dict[S, set[S]] = {
    S.DRAFT: {S.PENDING_APPROVAL, S.APPROVED, S.REJECTED, S.CANCELLED},
    S.PENDING_APPROVAL: {S.DRAFT, S.APPROVED, S.REJECTED, S.CANCELLED},
    S.APPROVED: {S.QUEUED, S.CANCELLED, S.PENDING_APPROVAL, S.FAILED},
    S.QUEUED: {S.SENDING, S.APPROVED, S.CANCELLED},
    S.SENDING: {S.SENT, S.APPROVED, S.FAILED, S.CANCELLED},
    S.SENT: {S.BOUNCED, S.COMPLAINED},
    S.BOUNCED: {S.COMPLAINED},
    S.FAILED: {S.APPROVED},  # manual retry after fixing the cause
    S.REJECTED: {S.DRAFT, S.PENDING_APPROVAL},
    S.CANCELLED: set(),
    S.COMPLAINED: set(),
}

# Messages in these states can still be stopped (reply received, unsubscribe, bounce ...).
CANCELLABLE = {S.DRAFT, S.PENDING_APPROVAL, S.APPROVED, S.QUEUED}
REVIEWABLE = {S.DRAFT, S.PENDING_APPROVAL}


class InvalidTransitionError(ValueError):
    pass


def transition(
    db: Session,
    message: EmailMessage,
    to: S,
    *,
    actor_id: int | None = None,
    reason: str | None = None,
    audit: bool = True,
) -> None:
    current = S(str(message.status))
    if current == to:
        return
    if to not in ALLOWED[current]:
        raise InvalidTransitionError(f"Cannot move email from {current} to {to}")
    message.status = to
    if audit:
        db.add(
            AuditLog(
                workspace_id=message.workspace_id,
                actor_id=actor_id,
                action=f"email_{to}",
                entity_type="email_message",
                entity_id=message.id,
                metadata_={"from": str(current), **({"reason": reason} if reason else {})},
            ),
        )
