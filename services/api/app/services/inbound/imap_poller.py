"""Poll IMAP inboxes (for SMTP senders without inbound webhooks)."""

from __future__ import annotations

import contextlib
import imaplib
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import system_session, workspace_scope
from app.models.enums import ProviderName, ProviderType
from app.models.inbound import InboxCursor
from app.models.provider_credential import ProviderCredential
from app.services.inbound.normalize import from_rfc822
from app.services.inbound.processor import process_inbound_email
from app.services.provider_credentials.service import decrypt_provider_config

logger = logging.getLogger(__name__)

BATCH = 100
TIMEOUT_SECONDS = 30
_UIDVALIDITY = re.compile(rb"UIDVALIDITY (\d+)")

ImapFactory = Callable[[dict[str, Any]], Any]


def default_imap_factory(config: dict[str, Any]) -> imaplib.IMAP4:
    host = str(config["host"])
    port = int(config.get("port") or 993)
    if config.get("use_ssl", True):
        return imaplib.IMAP4_SSL(host, port, timeout=TIMEOUT_SECONDS)
    client = imaplib.IMAP4(host, port, timeout=TIMEOUT_SECONDS)
    client.starttls()
    return client


def poll_credential(
    db: Session,
    credential: ProviderCredential,
    *,
    factory: ImapFactory = default_imap_factory,
) -> int:
    """Fetch new messages since the cursor and process them. Returns messages processed."""
    config = decrypt_provider_config(credential)
    cursor = db.scalar(select(InboxCursor).where(InboxCursor.credential_id == credential.id))
    if cursor is None:
        cursor = InboxCursor(workspace_id=credential.workspace_id, credential_id=credential.id)
        db.add(cursor)
        db.flush()

    processed = 0
    client = factory(config)
    try:
        client.login(str(config["username"]), str(config["password"]))
        status, data = client.select(str(config.get("folder") or "INBOX"), readonly=True)
        if status != "OK":
            raise RuntimeError("Could not open the mailbox folder")
        status, response = client.response("UIDVALIDITY")
        uidvalidity = None
        if response and response[0]:
            match = _UIDVALIDITY.search(response[0]) or re.search(rb"(\d+)", response[0])
            uidvalidity = int(match.group(1)) if match else None
        if uidvalidity is not None and cursor.uidvalidity not in (None, uidvalidity):
            logger.warning("UIDVALIDITY changed for credential %s; resetting cursor", credential.id)
            cursor.last_uid = 0
        cursor.uidvalidity = uidvalidity

        status, data = client.uid("search", None, f"UID {cursor.last_uid + 1}:*")
        uids = sorted(int(uid) for uid in (data[0] or b"").split() if int(uid) > cursor.last_uid)
        for uid in uids[:BATCH]:
            status, fetched = client.uid("fetch", str(uid), "(RFC822)")
            raw = next(
                (part[1] for part in fetched or [] if isinstance(part, tuple) and len(part) > 1),
                None,
            )
            if raw:
                try:
                    with workspace_scope(db, credential.workspace_id):
                        process_inbound_email(db, credential.workspace_id, from_rfc822(raw))
                    processed += 1
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Failed to process UID %s for credential %s", uid, credential.id
                    )
            cursor.last_uid = uid
            db.commit()
        cursor.last_error = None
    except Exception as exc:
        cursor.last_error = f"{exc.__class__.__name__}: {str(exc)[:400]}"
        logger.warning("IMAP poll failed for credential %s: %s", credential.id, exc)
    finally:
        cursor.last_polled_at = datetime.now(UTC)
        db.commit()
        with contextlib.suppress(Exception):  # best-effort disconnect
            client.logout()
    return processed


def poll_all_inboxes(db: Session, *, factory: ImapFactory = default_imap_factory) -> int:
    with system_session(db):
        credentials = db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.provider_type == ProviderType.INBOX,
                ProviderCredential.provider_name == ProviderName.IMAP,
                ProviderCredential.is_active.is_(True),
            ),
        ).all()
        total = 0
        for credential in credentials:
            total += poll_credential(db, credential, factory=factory)
    return total
