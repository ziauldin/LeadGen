"""Data subject requests (export / erase one person), workspace exports and retention."""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import secrets
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.storage import get_storage
from app.models.campaign import Campaign, CampaignStep
from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.email_template import EmailTemplateRecord
from app.models.enrollment import CampaignEnrollment
from app.models.enums import EmailMessageStatus
from app.models.inbound import EmailEvent, WebhookEvent
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.privacy import DataRequest
from app.models.reply import Reply
from app.models.suppression import Suppression
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.common.csv_safety import safe_cell
from app.services.workspaces.service import audit

EXPORT_TTL = timedelta(days=7)
WEBHOOK_PAYLOAD_RETENTION = timedelta(days=30)
CONTACTED_STATUSES = (
    EmailMessageStatus.SENT,
    EmailMessageStatus.BOUNCED,
    EmailMessageStatus.COMPLAINED,
)


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if "@" not in value or len(value) > 255:
        raise ValidationFailedError("Enter a valid email address")
    return value


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def row_dict(obj: Any) -> dict[str, Any]:
    """Plain column values for an ORM row, leaving out anything stored encrypted."""
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        if column.key.endswith("_encrypted"):
            continue
        attribute = "metadata_" if column.key == "metadata" else column.key
        value = getattr(obj, attribute, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.key] = value
    return data


def _put_zip(workspace_id: int, request: DataRequest, files: dict[str, str]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    key = f"workspaces/{workspace_id}/exports/{request.id}-{secrets.token_hex(8)}.zip"
    get_storage().put(key, buffer.getvalue(), "application/zip")
    request.file_key = key
    request.expires_at = datetime.now(UTC) + EXPORT_TTL


# --- one person ------------------------------------------------------------------------------


def _person_rows(db: Session, workspace_id: int, email: str) -> dict[str, list[Any]]:
    contacts = db.scalars(
        select(EmailContact).where(
            EmailContact.workspace_id == workspace_id, func.lower(EmailContact.email) == email
        )
    ).all()
    lead_ids = {c.lead_id for c in contacts if c.lead_id}
    leads = db.scalars(select(Lead).where(Lead.id.in_(lead_ids))).all() if lead_ids else []
    company_ids = {lead.company_id for lead in leads if lead.company_id}
    message_filter = [func.lower(EmailMessage.recipient_email) == email]
    if lead_ids:
        message_filter.append(EmailMessage.lead_id.in_(lead_ids))
    messages = db.scalars(
        select(EmailMessage).where(EmailMessage.workspace_id == workspace_id, or_(*message_filter))
    ).all()
    message_ids = {m.id for m in messages}
    reply_filter = [func.lower(Reply.from_email) == email]
    if lead_ids:
        reply_filter.append(Reply.lead_id.in_(lead_ids))
    if message_ids:
        reply_filter.append(Reply.email_message_id.in_(message_ids))
    return {
        "contacts": list(contacts),
        "leads": list(leads),
        "companies": list(db.scalars(select(Company).where(Company.id.in_(company_ids))).all())
        if company_ids
        else [],
        "messages": list(messages),
        "replies": list(
            db.scalars(
                select(Reply).where(Reply.workspace_id == workspace_id, or_(*reply_filter))
            ).all()
        ),
        "enrollments": list(
            db.scalars(
                select(CampaignEnrollment).where(CampaignEnrollment.lead_id.in_(lead_ids))
            ).all()
        )
        if lead_ids
        else [],
        "email_events": list(
            db.scalars(
                select(EmailEvent).where(
                    EmailEvent.workspace_id == workspace_id,
                    func.lower(EmailEvent.recipient_email) == email,
                )
            ).all()
        ),
        "suppressions": list(
            db.scalars(
                select(Suppression).where(
                    Suppression.workspace_id == workspace_id,
                    or_(Suppression.email == email, Suppression.email_hash == email_hash(email)),
                )
            ).all()
        ),
    }


PERSON_README = """Data export for {email}
Workspace: {workspace}
Created: {created}

person.json holds every record this workspace keeps about this email address:
contacts (where the address was found), leads (the person's profile and the lawful basis
for contacting them), companies, emails sent to them, their replies, campaign enrollments,
delivery events and any do-not-contact entries.
"""


def export_person(db: Session, request: DataRequest) -> None:
    email = request.subject_email or ""
    rows = _person_rows(db, request.workspace_id, email)
    workspace = db.get(Workspace, request.workspace_id)
    payload = {name: [row_dict(row) for row in items] for name, items in rows.items()}
    _put_zip(
        request.workspace_id,
        request,
        {
            "README.txt": PERSON_README.format(
                email=email,
                workspace=workspace.name if workspace else request.workspace_id,
                created=datetime.now(UTC).isoformat(),
            ),
            "person.json": json.dumps(payload, indent=2, default=str),
        },
    )
    request.summary = {name: len(items) for name, items in rows.items()}


def erase_person(db: Session, request: DataRequest) -> None:
    """Delete everything about one person, keeping only a hashed do-not-contact entry."""
    email = request.subject_email or ""
    hashed = email_hash(email)
    workspace_id = request.workspace_id
    rows = _person_rows(db, workspace_id, email)
    lead_ids = [lead.id for lead in rows["leads"]]
    message_ids = [m.id for m in rows["messages"]]
    summary = {name: len(items) for name, items in rows.items() if name != "suppressions"}

    if rows["replies"]:
        db.execute(delete(Reply).where(Reply.id.in_([r.id for r in rows["replies"]])))
    if rows["email_events"]:
        db.execute(
            delete(EmailEvent).where(EmailEvent.id.in_([e.id for e in rows["email_events"]]))
        )
    if message_ids:
        db.execute(
            update(Suppression)
            .where(Suppression.email_message_id.in_(message_ids))
            .values(email_message_id=None)
        )
        db.execute(delete(EmailMessage).where(EmailMessage.id.in_(message_ids)))
    if lead_ids:
        db.execute(delete(CampaignEnrollment).where(CampaignEnrollment.lead_id.in_(lead_ids)))
    if rows["contacts"]:
        db.execute(
            delete(EmailContact).where(EmailContact.id.in_([c.id for c in rows["contacts"]]))
        )
    if lead_ids:
        db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))

    # Swap any readable do-not-contact entry for a hashed one, so they stay blocked.
    db.execute(
        delete(Suppression).where(
            Suppression.workspace_id == workspace_id, Suppression.email == email
        )
    )
    if not db.scalar(
        select(Suppression.id).where(
            Suppression.workspace_id == workspace_id, Suppression.email_hash == hashed
        )
    ):
        db.add(
            Suppression(
                workspace_id=workspace_id,
                email=None,
                email_hash=hashed,
                reason="Erased at the person's request",
                reason_code="erasure",
                source="privacy",
            )
        )

    # Earlier exports for this person go too.
    for earlier in db.scalars(
        select(DataRequest).where(
            DataRequest.workspace_id == workspace_id,
            DataRequest.subject_hash == hashed,
            DataRequest.id != request.id,
        )
    ).all():
        _delete_file(earlier)
        earlier.subject_email = None

    request.subject_email = None
    request.summary = summary


# --- whole workspace -------------------------------------------------------------------------


def _csv(rows: list[Any]) -> str:
    buffer = io.StringIO()
    if not rows:
        return ""
    dicts = [row_dict(row) for row in rows]
    writer = csv.DictWriter(buffer, fieldnames=list(dicts[0].keys()))
    writer.writeheader()
    for item in dicts:
        writer.writerow(
            {
                k: safe_cell(json.dumps(v) if isinstance(v, (dict, list)) else v)
                for k, v in item.items()
            }
        )
    return buffer.getvalue()


WORKSPACE_TABLES: dict[str, Any] = {
    "niches": Niche,
    "companies": Company,
    "leads": Lead,
    "email_contacts": EmailContact,
    "campaigns": Campaign,
    "campaign_steps": CampaignStep,
    "campaign_enrollments": CampaignEnrollment,
    "email_templates": EmailTemplateRecord,
    "email_messages": EmailMessage,
    "replies": Reply,
    "suppressions": Suppression,
}


def export_workspace(db: Session, request: DataRequest) -> None:
    files: dict[str, str] = {}
    summary: dict[str, int] = {}
    for name, model in WORKSPACE_TABLES.items():
        rows = list(
            db.scalars(select(model).where(model.workspace_id == request.workspace_id)).all()
        )
        files[f"{name}.csv"] = _csv(rows)
        summary[name] = len(rows)
    files["README.txt"] = (
        "Full export of this LeadsGen workspace, one CSV per table.\n"
        f"Created {datetime.now(UTC).isoformat()}. Provider credentials are not included.\n"
    )
    _put_zip(request.workspace_id, request, files)
    request.summary = summary


# --- requests --------------------------------------------------------------------------------


def create_request(
    db: Session, *, workspace_id: int, actor_id: int, kind: str, email: str | None, note: str | None
) -> DataRequest:
    subject: str | None = None
    if kind in ("export", "erase"):
        if not email:
            raise ValidationFailedError("Enter the person's email address")
        subject = normalize_email(email)
    request = DataRequest(
        workspace_id=workspace_id,
        kind=kind,
        subject_email=subject,
        subject_hash=email_hash(subject) if subject else None,
        requested_by_id=actor_id,
        note=note,
        status="pending",
    )
    db.add(request)
    db.flush()
    audit(
        db,
        workspace_id,
        actor_id,
        f"privacy.{kind}_requested",
        "data_request",
        request.id,
        {"subject_hash": request.subject_hash} if subject else None,
    )
    db.commit()
    return request


HANDLERS = {"export": export_person, "erase": erase_person, "workspace_export": export_workspace}


def process_request(db: Session, request_id: int) -> DataRequest | None:
    request = db.get(DataRequest, request_id)
    if request is None or request.status not in ("pending", "failed"):
        return request
    request.status = "running"
    db.commit()
    try:
        HANDLERS[request.kind](db, request)
    except Exception as exc:
        db.rollback()
        request = db.get(DataRequest, request_id)
        assert request is not None  # noqa: S101
        request.status = "failed"
        request.error = str(exc)[:1000]
        db.commit()
        raise
    request.status = "completed"
    request.completed_at = datetime.now(UTC)
    request.error = None
    audit(
        db,
        request.workspace_id,
        request.requested_by_id,
        f"privacy.{request.kind}_completed",
        "data_request",
        request.id,
        {"subject_hash": request.subject_hash, **(request.summary or {})},
    )
    db.commit()
    return request


def _delete_file(request: DataRequest) -> None:
    if request.file_key:
        with contextlib.suppress(Exception):  # already gone is fine
            get_storage().delete(request.file_key)
        request.file_key = None


def purge_expired_exports(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    expired = db.scalars(
        select(DataRequest).where(DataRequest.file_key.is_not(None), DataRequest.expires_at < now)
    ).all()
    for request in expired:
        _delete_file(request)
    db.commit()
    return len(expired)


# --- retention -------------------------------------------------------------------------------


def apply_retention(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Run every workspace's retention rules. Call inside a system (cross-tenant) session."""
    now = now or datetime.now(UTC)
    totals = {"leads": 0, "replies": 0, "webhook_events": 0}
    for settings_row in db.scalars(
        select(WorkspaceSettings).where(
            or_(
                WorkspaceSettings.retention_uncontacted_lead_days.is_not(None),
                WorkspaceSettings.retention_reply_days.is_not(None),
            )
        )
    ).all():
        workspace_id = settings_row.workspace_id
        if settings_row.retention_uncontacted_lead_days:
            cutoff = now - timedelta(days=settings_row.retention_uncontacted_lead_days)
            contacted = exists().where(
                EmailMessage.lead_id == Lead.id, EmailMessage.status.in_(CONTACTED_STATUSES)
            )
            stale = db.scalars(
                select(Lead.id).where(
                    Lead.workspace_id == workspace_id, Lead.created_at < cutoff, ~contacted
                )
            ).all()
            if stale:
                db.execute(delete(Lead).where(Lead.id.in_(stale)))
                totals["leads"] += len(stale)
                audit(
                    db,
                    workspace_id,
                    None,
                    "privacy.retention_leads_deleted",
                    "workspace",
                    workspace_id,
                    {"count": len(stale)},
                )
        if settings_row.retention_reply_days:
            cutoff = now - timedelta(days=settings_row.retention_reply_days)
            result = db.execute(
                delete(Reply).where(Reply.workspace_id == workspace_id, Reply.received_at < cutoff)
            )
            removed = result.rowcount or 0  # type: ignore[attr-defined]
            if removed:
                totals["replies"] += removed
                audit(
                    db,
                    workspace_id,
                    None,
                    "privacy.retention_replies_deleted",
                    "workspace",
                    workspace_id,
                    {"count": removed},
                )
    # Raw provider payloads can contain addresses; keep them only as long as debugging needs.
    result = db.execute(
        delete(WebhookEvent).where(
            WebhookEvent.received_at < now - WEBHOOK_PAYLOAD_RETENTION,
            WebhookEvent.status != "pending",
        )
    )
    totals["webhook_events"] = result.rowcount or 0  # type: ignore[attr-defined]
    db.commit()
    return totals
