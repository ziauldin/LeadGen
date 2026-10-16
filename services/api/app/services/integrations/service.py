"""CRM integrations: connect HubSpot or Pipedrive, push contacts and deals, pull deal status.

Pushes are queued in the caller's transaction and run by a Celery task once it commits, so a
slow or failing CRM never blocks the app. Every push and pull is written to the sync log.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import event, select
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.flags import feature_enabled
from app.core.security import decrypt_secret_payload, encrypt_secret_payload
from app.models.crm import Deal, DealStage
from app.models.email_contact import EmailContact
from app.models.enums import ReplyClassification
from app.models.integration import IntegrationConnection, IntegrationLink, IntegrationSyncLog
from app.models.lead import Lead
from app.models.reply import Reply
from app.models.workspace import Workspace
from app.services.billing.plans import features_for
from app.services.integrations.clients import (
    ContactData,
    CrmClient,
    DealData,
    HubSpotClient,
    IntegrationError,
    PipedriveClient,
    hubspot_configured,
    normalize_pipedrive_domain,
)
from app.services.workspaces.service import audit

logger = logging.getLogger(__name__)

PROVIDERS: dict[str, dict[str, str]] = {
    "hubspot": {"label": "HubSpot", "auth": "oauth"},
    "pipedrive": {"label": "Pipedrive", "auth": "token"},
}
DEFAULT_SETTINGS = {"push_contacts": True, "push_deals": True, "pull_status": True}
SETTING_FOR = {"contact": "push_contacts", "deal": "push_deals"}
PENDING_KEY = "integration_sync_pending"
STATE_TYPE = "integration_oauth"
STATE_TTL = timedelta(minutes=10)
FULL_SYNC_LIMIT = 500


def _now() -> datetime:
    return datetime.now(UTC)


def allowed(workspace: Workspace) -> bool:
    return feature_enabled("integrations", workspace) and features_for(workspace).integrations


def provider_available(name: str) -> bool:
    return name == "pipedrive" or (name == "hubspot" and hubspot_configured())


def settings_of(connection: IntegrationConnection) -> dict[str, bool]:
    return {**DEFAULT_SETTINGS, **(connection.settings or {})}


def _config(connection: IntegrationConnection) -> dict[str, Any]:
    return dict(json.loads(decrypt_secret_payload(connection.config_encrypted)))


def _store(connection: IntegrationConnection, config: dict[str, Any]) -> None:
    connection.config_encrypted = encrypt_secret_payload(json.dumps(config))


def client_for(connection: IntegrationConnection) -> CrmClient:
    config = _config(connection)
    if connection.provider == "hubspot":
        return HubSpotClient(config, on_tokens=lambda fresh: _store(connection, fresh))
    if connection.provider == "pipedrive":
        return PipedriveClient(config)
    raise IntegrationError(f"Unknown integration {connection.provider}")


# --- Connections -----------------------------------------------------------------------------


def list_connections(db: Session, workspace_id: int) -> list[IntegrationConnection]:
    return list(
        db.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.workspace_id == workspace_id)
            .order_by(IntegrationConnection.provider)
        ).all()
    )


def get_connection(db: Session, workspace_id: int, connection_id: int) -> IntegrationConnection:
    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.workspace_id == workspace_id,
        )
    )
    if connection is None:
        raise NotFoundError("Integration not found")
    return connection


def connect(
    db: Session, workspace_id: int, user_id: int | None, provider: str, config: dict[str, Any]
) -> IntegrationConnection:
    """Check the credentials against the CRM, then store them (encrypted)."""
    if provider == "pipedrive":
        try:
            config = {
                **config,
                "company_domain": normalize_pipedrive_domain(config["company_domain"]),
            }
        except IntegrationError as exc:
            raise ValidationFailedError(str(exc)) from exc
        client: CrmClient = PipedriveClient(config)
    elif provider == "hubspot":
        client = HubSpotClient(config, on_tokens=config.update)
    else:
        raise ValidationFailedError("Unknown integration")
    try:
        label = client.account_label()
    except IntegrationError as exc:
        raise ValidationFailedError(f"Couldn't connect: {exc}") from exc

    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.workspace_id == workspace_id,
            IntegrationConnection.provider == provider,
        )
    )
    if connection is None:
        connection = IntegrationConnection(
            workspace_id=workspace_id, provider=provider, settings=dict(DEFAULT_SETTINGS)
        )
        db.add(connection)
    _store(connection, config)
    connection.account_label = label[:255]
    connection.status = "active"
    connection.last_error = None
    connection.connected_by_id = user_id
    db.flush()
    audit(
        db,
        workspace_id,
        user_id,
        "integration_connected",
        "integration",
        connection.id,
        {"provider": provider, "account": connection.account_label},
    )
    db.commit()
    return connection


def update_settings(
    db: Session, connection: IntegrationConnection, actor_id: int, changes: dict[str, bool]
) -> IntegrationConnection:
    connection.settings = {**settings_of(connection), **changes}
    audit(
        db,
        connection.workspace_id,
        actor_id,
        "integration_updated",
        "integration",
        connection.id,
        changes,
    )
    db.commit()
    return connection


def disconnect(db: Session, connection: IntegrationConnection, actor_id: int) -> None:
    audit(
        db,
        connection.workspace_id,
        actor_id,
        "integration_disconnected",
        "integration",
        connection.id,
        {"provider": connection.provider},
    )
    db.delete(connection)
    db.commit()


def recent_logs(
    db: Session, connection: IntegrationConnection, limit: int = 50
) -> list[IntegrationSyncLog]:
    return list(
        db.scalars(
            select(IntegrationSyncLog)
            .where(IntegrationSyncLog.connection_id == connection.id)
            .order_by(IntegrationSyncLog.id.desc())
            .limit(limit)
        ).all()
    )


# --- OAuth state (HubSpot) -------------------------------------------------------------------


@dataclass
class OAuthState:
    workspace_id: int
    user_id: int


def state_token(workspace_id: int, user_id: int) -> str:
    now = _now()
    return jwt.encode(
        {
            "typ": STATE_TYPE,
            "wsp": workspace_id,
            "sub": str(user_id),
            "nonce": secrets.token_hex(8),
            "iat": now,
            "exp": now + STATE_TTL,
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def read_state(token: str) -> OAuthState:
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationFailedError("This connection link has expired. Please try again.") from exc
    if claims.get("typ") != STATE_TYPE:
        raise ValidationFailedError("This connection link is invalid. Please try again.")
    return OAuthState(workspace_id=int(claims["wsp"]), user_id=int(claims["sub"]))


# --- Pushing ---------------------------------------------------------------------------------


def _log(
    db: Session,
    connection: IntegrationConnection,
    direction: str,
    object_type: str,
    local_id: int | None,
    remote_id: str | None,
    status: str,
    message: str | None = None,
) -> None:
    db.add(
        IntegrationSyncLog(
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
            direction=direction,
            object_type=object_type,
            local_id=local_id,
            remote_id=remote_id,
            status=status,
            message=(message or "")[:500] or None,
        )
    )


def _link(
    db: Session, connection: IntegrationConnection, object_type: str, local_id: int
) -> IntegrationLink | None:
    return db.scalar(
        select(IntegrationLink).where(
            IntegrationLink.connection_id == connection.id,
            IntegrationLink.object_type == object_type,
            IntegrationLink.local_id == local_id,
        )
    )


def _save_link(
    db: Session,
    connection: IntegrationConnection,
    object_type: str,
    local_id: int,
    remote_id: str,
    remote_status: str | None = None,
) -> None:
    link = _link(db, connection, object_type, local_id)
    if link is None:
        link = IntegrationLink(
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
            object_type=object_type,
            local_id=local_id,
            remote_id=remote_id,
        )
        db.add(link)
    link.remote_id = remote_id
    link.synced_at = _now()
    if remote_status is not None:
        link.remote_status = remote_status
    db.flush()


def _contact_data(db: Session, lead: Lead) -> ContactData | None:
    email = db.scalar(
        select(EmailContact.email)
        .where(EmailContact.lead_id == lead.id, EmailContact.workspace_id == lead.workspace_id)
        .order_by(EmailContact.id)
        .limit(1)
    )
    if not email:
        return None
    return ContactData(
        email=email.lower(),
        full_name=lead.full_name,
        job_title=lead.job_title,
        company=lead.company.name if lead.company else None,
    )


def push_contact(
    db: Session, connection: IntegrationConnection, client: CrmClient, lead: Lead
) -> str | None:
    contact = _contact_data(db, lead)
    if contact is None:
        _log(db, connection, "push", "contact", lead.id, None, "skipped", "The lead has no email")
        return None
    link = _link(db, connection, "contact", lead.id)
    remote_id = client.upsert_contact(contact, link.remote_id if link else None)
    _save_link(db, connection, "contact", lead.id, remote_id)
    _log(db, connection, "push", "contact", lead.id, remote_id, "ok")
    return remote_id


def push_deal(db: Session, connection: IntegrationConnection, client: CrmClient, deal: Deal) -> str:
    kind = db.scalar(select(DealStage.kind).where(DealStage.id == deal.stage_id)) or "open"
    contact_id = None
    if deal.lead_id:
        lead = db.get(Lead, deal.lead_id)
        if lead is not None:
            # A deal is linked to its contact, so the contact goes too.
            contact_id = push_contact(db, connection, client, lead)
    link = _link(db, connection, "deal", deal.id)
    remote_id = client.upsert_deal(
        DealData(
            title=deal.title,
            value=deal.value_cents / 100,
            currency=deal.currency,
            kind=kind,
            close_date=deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        ),
        contact_id,
        link.remote_id if link else None,
    )
    _save_link(db, connection, "deal", deal.id, remote_id, kind)
    _log(db, connection, "push", "deal", deal.id, remote_id, "ok")
    return remote_id


def _fail(
    db: Session,
    connection: IntegrationConnection,
    exc: IntegrationError,
    direction: str,
    object_type: str,
    local_id: int | None,
) -> None:
    _log(db, connection, direction, object_type, local_id, None, "error", str(exc))
    connection.last_error = str(exc)[:1000]
    if exc.auth:
        connection.status = "error"


def sync_object(
    db: Session, connection: IntegrationConnection, object_type: str, local_id: int
) -> str:
    """Push one lead (``contact``) or deal. Returns ok | skipped | error."""
    if connection.status != "active":
        return "skipped"
    try:
        client = client_for(connection)
        if object_type == "contact":
            lead = db.get(Lead, local_id)
            if lead is None or lead.workspace_id != connection.workspace_id:
                return "skipped"
            result = "ok" if push_contact(db, connection, client, lead) else "skipped"
        elif object_type == "deal":
            deal = db.get(Deal, local_id)
            if deal is None or deal.workspace_id != connection.workspace_id:
                return "skipped"
            push_deal(db, connection, client, deal)
            result = "ok"
        else:
            raise ValueError(f"Unknown object type {object_type}")
        connection.last_synced_at = _now()
        connection.last_error = None
    except IntegrationError as exc:
        _fail(db, connection, exc, "push", object_type, local_id)
        result = "error"
    db.commit()
    return result


def sync_all(db: Session, connection: IntegrationConnection) -> dict[str, int]:
    """Push interested leads and every deal (up to FULL_SYNC_LIMIT of each)."""
    options = settings_of(connection)
    counts = {"ok": 0, "skipped": 0, "error": 0}
    if options["push_contacts"]:
        lead_ids = db.scalars(
            select(Reply.lead_id)
            .where(
                Reply.workspace_id == connection.workspace_id,
                Reply.lead_id.is_not(None),
                Reply.classification == ReplyClassification.POSITIVE,
                Reply.is_auto_reply.is_(False),
            )
            .distinct()
            .limit(FULL_SYNC_LIMIT)
        ).all()
        for lead_id in lead_ids:
            if lead_id is not None:
                counts[sync_object(db, connection, "contact", lead_id)] += 1
    if options["push_deals"]:
        deal_ids = db.scalars(
            select(Deal.id)
            .where(Deal.workspace_id == connection.workspace_id)
            .order_by(Deal.id)
            .limit(FULL_SYNC_LIMIT)
        ).all()
        for deal_id in deal_ids:
            counts[sync_object(db, connection, "deal", deal_id)] += 1
    return counts


# --- Pulling deal status ---------------------------------------------------------------------


def pull_statuses(db: Session, connection: IntegrationConnection) -> int:
    """Close local deals that were won or lost in the CRM. Returns how many moved."""
    if connection.status != "active" or not settings_of(connection)["pull_status"]:
        return 0
    links = list(
        db.scalars(
            select(IntegrationLink).where(
                IntegrationLink.connection_id == connection.id,
                IntegrationLink.object_type == "deal",
            )
        ).all()
    )
    if not links:
        return 0
    try:
        statuses = client_for(connection).deal_statuses([link.remote_id for link in links])
    except IntegrationError as exc:
        _fail(db, connection, exc, "pull", "deal", None)
        db.commit()
        return 0
    closing = {
        kind: db.scalar(
            select(DealStage)
            .where(DealStage.workspace_id == connection.workspace_id, DealStage.kind == kind)
            .order_by(DealStage.position)
            .limit(1)
        )
        for kind in ("won", "lost")
    }
    moved = 0
    for link in links:
        status = statuses.get(link.remote_id)
        if status is None or status == link.remote_status:
            continue
        link.remote_status = status
        deal = db.get(Deal, link.local_id)
        target = closing.get(status)
        if deal is None or target is None or deal.stage_id == target.id:
            continue
        current_kind = db.scalar(select(DealStage.kind).where(DealStage.id == deal.stage_id))
        if current_kind == status:
            continue
        deal.stage_id = target.id
        deal.closed_at = _now()
        audit(
            db,
            connection.workspace_id,
            None,
            "deal_updated",
            "deal",
            deal.id,
            {"to_stage": target.name, "source": connection.provider},
        )
        _log(db, connection, "pull", "deal", deal.id, link.remote_id, "ok", f"Marked {status}")
        moved += 1
    connection.last_synced_at = _now()
    db.commit()
    return moved


# --- Queueing from app events ----------------------------------------------------------------


def queue(db: Session, workspace_id: int, object_type: str, local_id: int) -> None:
    """Push this lead or deal to every connected CRM once the current transaction commits."""
    setting = SETTING_FOR[object_type]
    connections = db.scalars(
        select(IntegrationConnection).where(
            IntegrationConnection.workspace_id == workspace_id,
            IntegrationConnection.status == "active",
        )
    ).all()
    pending = db.info.setdefault(PENDING_KEY, [])
    for connection in connections:
        if settings_of(connection)[setting]:
            item = (connection.id, object_type, local_id)
            if item not in pending:
                pending.append(item)


def on_positive_reply(db: Session, reply: Reply) -> None:
    if (
        reply.lead_id is not None
        and not reply.is_auto_reply
        and str(reply.classification) == ReplyClassification.POSITIVE
    ):
        queue(db, reply.workspace_id, "contact", reply.lead_id)


@event.listens_for(Session, "after_transaction_end")
def _sync_after_commit(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is not None or transaction.nested:
        return
    items = session.info.pop(PENDING_KEY, None)
    if not items:
        return
    from app.workers.integration_jobs import sync_integration_object

    for connection_id, object_type, local_id in items:
        try:
            sync_integration_object.delay(connection_id, object_type, local_id)
        except Exception:
            logger.exception("Could not queue %s %s for integration sync", object_type, local_id)


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session: Session) -> None:
    session.info.pop(PENDING_KEY, None)
