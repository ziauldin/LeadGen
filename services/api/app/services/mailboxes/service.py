"""Connected mailboxes: create the credential after OAuth, send through it, sync replies,
watch its health, and pick which mailbox sends each email (rotation)."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import (
    EmailMessageStatus,
    ProviderCredentialStatus,
    ProviderName,
    ProviderType,
)
from app.models.mailbox import CampaignSender
from app.models.provider_credential import ProviderCredential
from app.models.workspace import Workspace
from app.services.billing.usage import check_mailbox_limit
from app.services.mailboxes import clients, oauth
from app.services.provider_credentials.service import _as_str
from app.services.sending.base import OutboundEmail, SendKind, SendResult
from app.services.sending.external_providers import SmtpEmailSender
from app.services.sending.warmup import daily_cap
from app.services.workspaces.service import audit

logger = logging.getLogger(__name__)

MAILBOX_PROVIDERS = {ProviderName.GMAIL.value, ProviderName.OUTLOOK.value}
SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)
# Health: pause a mailbox when this share of its recent sends bounce or complain.
HEALTH_WINDOW = 50
HEALTH_MIN_SENDS = 20
MAX_BOUNCE_RATE = 0.08
MAX_COMPLAINT_RATE = 0.005
DEFAULT_MAILBOX_DAILY_LIMIT = 50


def is_mailbox(credential: ProviderCredential | None) -> bool:
    return credential is not None and _as_str(credential.provider_name) in MAILBOX_PROVIDERS


def complete_connection(db: Session, state: oauth.OAuthState, code: str) -> ProviderCredential:
    """Exchange the code, read the mailbox address and save (or update) its credential."""
    tokens = oauth.exchange_code(state.provider, code, state.verifier)
    if not tokens.get("refresh_token"):
        raise oauth.MailboxAuthError("The provider didn't grant offline access. Please try again.")
    client = (
        clients.GmailClient(tokens["access_token"])
        if state.provider == "gmail"
        else clients.GraphClient(tokens["access_token"])
    )
    email = client.profile_email()
    config = {
        "from_email": email,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": oauth.expires_at(tokens),
    }
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == state.workspace_id,
            ProviderCredential.provider_type == ProviderType.EMAIL,
            ProviderCredential.provider_name == state.provider,
            ProviderCredential.display_name == email,
        )
    )
    if credential is None:
        workspace = db.get(Workspace, state.workspace_id)
        if workspace is not None:
            check_mailbox_limit(db, workspace)  # reconnecting an existing mailbox is always allowed
        credential = ProviderCredential(
            workspace_id=state.workspace_id,
            user_id=state.user_id,
            provider_type=ProviderType.EMAIL,
            provider_name=state.provider,
            display_name=email,
            webhook_token=secrets.token_urlsafe(24),
            warmup_enabled=True,
            warmup_started_at=datetime.now(UTC),
            daily_limit=DEFAULT_MAILBOX_DAILY_LIMIT,
        )
        db.add(credential)
    clients.save_config(credential, config)
    credential.masked_summary = f"{oauth.PROVIDERS[state.provider].label}: {email}"
    credential.status = ProviderCredentialStatus.CONFIGURED
    credential.disabled_at = None
    credential.disabled_reason = None
    credential.last_test_status = "success"
    credential.last_test_message = "Connected"
    credential.last_tested_at = datetime.now(UTC)
    db.flush()
    audit(
        db,
        state.workspace_id,
        state.user_id,
        "mailbox_connected",
        "provider_credential",
        credential.id,
        {"provider": state.provider, "email": email},
    )
    db.commit()
    return credential


def mark_needs_reconnect(db: Session, credential: ProviderCredential, reason: str) -> None:
    credential.status = ProviderCredentialStatus.ERROR
    credential.disabled_at = datetime.now(UTC)
    credential.disabled_reason = f"Reconnect needed: {reason}"[:255]
    credential.last_test_status = "error"
    credential.last_test_message = credential.disabled_reason
    audit(
        db,
        credential.workspace_id,
        None,
        "mailbox_disconnected",
        "provider_credential",
        credential.id,
        {"reason": reason[:200]},
    )


class MailboxEmailSender:
    """Sends through the Gmail API or Microsoft Graph as a MIME message (threading kept)."""

    def __init__(
        self, credential: ProviderCredential, from_email: str, from_name: str | None
    ) -> None:
        self.credential = credential
        self.provider_name = _as_str(credential.provider_name)
        self.from_email = from_email
        self.from_name = from_name
        self._mime = SmtpEmailSender(
            host="", port=0, username="", password="", from_email=from_email, from_name=from_name
        )

    def send(self, email: OutboundEmail) -> SendResult:
        raw = self._mime.build_mime(email).as_bytes()
        try:
            provider_id = clients.client_for(self.credential).send_raw(raw)
        except oauth.MailboxAuthError as exc:
            self.credential.status = ProviderCredentialStatus.ERROR
            self.credential.disabled_at = datetime.now(UTC)
            self.credential.disabled_reason = f"Reconnect needed: {exc}"[:255]
            return SendResult(kind=SendKind.TRANSIENT, error="Mailbox needs to be reconnected")
        except clients.MailboxError as exc:
            return SendResult(
                kind=SendKind.TRANSIENT if exc.transient else SendKind.PERMANENT,
                error=str(exc)[:255],
            )
        return SendResult(kind=SendKind.OK, provider_message_id=provider_id or email.message_id)


# --- rotation ------------------------------------------------------------------------------------


def usable(credential: ProviderCredential) -> bool:
    return (
        credential.disabled_at is None
        and _as_str(credential.status) != ProviderCredentialStatus.ERROR
    )


def effective_cap(credential: ProviderCredential, now: datetime) -> int | None:
    caps = [
        c
        for c in (daily_cap(credential, now.astimezone(UTC).date()), credential.daily_limit)
        if c is not None
    ]
    return min(caps) if caps else None


def _sent_today(db: Session, credential_id: int, now: datetime) -> int:
    start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.sender_credential_id == credential_id,
                EmailMessage.status.in_(SENT_LIKE),
                EmailMessage.sent_at >= start,
            )
        )
        or 0
    )


def pool(db: Session, campaign: Campaign) -> list[ProviderCredential]:
    return list(
        db.scalars(
            select(ProviderCredential)
            .join(CampaignSender, CampaignSender.credential_id == ProviderCredential.id)
            .where(CampaignSender.campaign_id == campaign.id)
            .order_by(ProviderCredential.id)
        ).all()
    )


def choose_credential(
    db: Session, campaign: Campaign, message: EmailMessage, now: datetime
) -> ProviderCredential | None:
    """Which mailbox sends this message, or None to fall back to the campaign/default sender.

    Follow-ups go out from the mailbox that sent the first email to that lead, so the thread
    stays together. Otherwise the healthy pool mailbox with the most room left today wins.
    """
    senders = pool(db, campaign)
    if not senders:
        return None
    if message.enrollment_id is not None:
        previous = db.scalar(
            select(EmailMessage.sender_credential_id)
            .where(
                EmailMessage.enrollment_id == message.enrollment_id,
                EmailMessage.id != message.id,
                EmailMessage.sender_credential_id.is_not(None),
                EmailMessage.status.in_(SENT_LIKE),
            )
            .order_by(EmailMessage.sent_at.asc())
            .limit(1)
        )
        if previous is not None:
            match = next((c for c in senders if c.id == previous), None) or db.get(
                ProviderCredential, previous
            )
            if match is not None and usable(match):
                return match
    healthy = [c for c in senders if usable(c)]
    if not healthy:
        return senders[0]  # the gate defers or fails the send with a clear reason

    def room(credential: ProviderCredential) -> float:
        cap = effective_cap(credential, now)
        sent = _sent_today(db, credential.id, now)
        return float("inf") if cap is None else cap - sent

    return max(healthy, key=lambda c: (room(c), -c.id))


def set_campaign_senders(
    db: Session, campaign: Campaign, credential_ids: list[int]
) -> list[ProviderCredential]:
    credentials = list(
        db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.id.in_(credential_ids),
                ProviderCredential.workspace_id == campaign.workspace_id,
                ProviderCredential.provider_type == ProviderType.EMAIL,
            )
        ).all()
    )
    if len(credentials) != len(set(credential_ids)):
        from app.core.errors import ValidationFailedError

        raise ValidationFailedError("Choose sending accounts from this workspace")
    for row in db.scalars(
        select(CampaignSender).where(CampaignSender.campaign_id == campaign.id)
    ).all():
        db.delete(row)
    db.flush()
    for credential in credentials:
        db.add(
            CampaignSender(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                credential_id=credential.id,
            )
        )
    db.commit()
    return credentials


# --- health and inbox sync ---------------------------------------------------------------------


def check_health(db: Session, credential: ProviderCredential) -> str | None:
    """Pause a mailbox whose recent sends bounce or get marked as spam too often."""
    recent = (
        db.execute(
            select(EmailMessage.status)
            .where(
                EmailMessage.sender_credential_id == credential.id,
                EmailMessage.status.in_(SENT_LIKE),
            )
            .order_by(EmailMessage.sent_at.desc())
            .limit(HEALTH_WINDOW)
        )
        .scalars()
        .all()
    )
    if len(recent) < HEALTH_MIN_SENDS or credential.disabled_at is not None:
        return None
    bounce = sum(1 for s in recent if s == EmailMessageStatus.BOUNCED) / len(recent)
    complaint = sum(1 for s in recent if s == EmailMessageStatus.COMPLAINED) / len(recent)
    if bounce > MAX_BOUNCE_RATE or complaint > MAX_COMPLAINT_RATE:
        credential.disabled_at = datetime.now(UTC)
        credential.disabled_reason = f"Paused: {bounce:.0%} bounces, {complaint:.1%} complaints in the last {len(recent)} sends"
        audit(
            db,
            credential.workspace_id,
            None,
            "mailbox_paused",
            "provider_credential",
            credential.id,
            {"bounce_rate": bounce, "complaint_rate": complaint},
        )
        return credential.disabled_reason
    return None


def sync_inbox(db: Session, credential: ProviderCredential) -> int:
    """Fetch new inbox mail since the last cursor and feed it to the reply pipeline."""
    from app.services.inbound.normalize import from_rfc822
    from app.services.inbound.processor import process_inbound_email

    if not usable(credential):
        return 0
    try:
        client = clients.client_for(credential)
        config = clients.config_of(credential)
        raw_messages, cursor = client.fetch_new(config.get("sync_cursor"))
    except oauth.MailboxAuthError as exc:
        mark_needs_reconnect(db, credential, str(exc))
        db.commit()
        return 0
    except clients.MailboxError as exc:
        logger.warning("Mailbox %s sync failed: %s", credential.id, exc)
        return 0
    processed = 0
    for raw in raw_messages:
        try:
            process_inbound_email(db, credential.workspace_id, from_rfc822(raw))
            processed += 1
        except Exception:
            db.rollback()
            logger.exception("Could not process a message from mailbox %s", credential.id)
    config = clients.config_of(credential)
    config["sync_cursor"] = cursor
    config["last_synced_at"] = datetime.now(UTC).isoformat()
    clients.save_config(credential, config)
    db.commit()
    return processed


def mailboxes_to_sync(db: Session) -> list[ProviderCredential]:
    return list(
        db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.provider_type == ProviderType.EMAIL,
                ProviderCredential.provider_name.in_(MAILBOX_PROVIDERS),
                ProviderCredential.disabled_at.is_(None),
            )
        ).all()
    )


def stale(credential: ProviderCredential, minutes: int = 10) -> bool:
    last = clients.config_of(credential).get("last_synced_at")
    return not last or datetime.fromisoformat(last) < datetime.now(UTC) - timedelta(minutes=minutes)
