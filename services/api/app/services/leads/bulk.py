"""Bulk lead actions. Each lead succeeds or fails on its own and the outcome is reported."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, ValidationFailedError
from app.core.tenancy import WorkspaceContext
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.schemas.common import BulkResult
from app.schemas.lead import LeadBulkRequest, LeadStats
from app.services.campaigns.service import add_leads_to_campaign
from app.services.enrichment.queueing import queue_enrichment
from app.services.leads.status import validate_user_status_change
from app.services.scoring.lead_score import apply_score_result, score_lead
from app.services.workspaces.service import audit

CONTACTED = (
    EmailMessageStatus.SENDING,
    EmailMessageStatus.SENT,
    EmailMessageStatus.BOUNCED,
    EmailMessageStatus.COMPLAINED,
)


def delete_lead(db: Session, lead: Lead) -> None:
    """Delete a lead and its unsent drafts. Leads that were emailed are kept for the record."""
    contacted = db.scalar(
        select(EmailMessage.id)
        .where(EmailMessage.lead_id == lead.id, EmailMessage.status.in_(CONTACTED))
        .limit(1),
    )
    if contacted is not None:
        raise ValidationFailedError(
            "This lead has been emailed, so it's kept for the record. Disqualify it instead.",
        )
    db.delete(lead)


def _load(db: Session, workspace_id: int, lead_ids: list[int]) -> dict[int, Lead]:
    leads = db.scalars(
        select(Lead)
        .where(Lead.workspace_id == workspace_id, Lead.id.in_(lead_ids))
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    ).all()
    return {lead.id: lead for lead in leads}


def _enrich(db: Session, ctx: WorkspaceContext, ids: list[int], result: BulkResult) -> None:
    leads = _load(db, ctx.workspace_id, ids)
    queued: set[int] = set()
    for lead_id in ids:
        lead = leads.get(lead_id)
        if lead is None:
            result.skip(lead_id, "Lead not found")
        elif lead.company is None:
            result.skip(lead_id, "Lead has no company")
        elif lead.company_id in queued:
            result.ok(lead_id, "Company already queued")
        else:
            try:
                queue_enrichment(db, ctx.workspace, lead.company)
            except AppError as exc:
                result.fail(lead_id, exc.detail)
                continue
            queued.add(lead.company.id)
            result.ok(lead_id, "Company enrichment queued")


def _per_lead(
    db: Session,
    ctx: WorkspaceContext,
    payload: LeadBulkRequest,
    ids: list[int],
    result: BulkResult,
) -> None:
    leads = _load(db, ctx.workspace_id, ids)
    niches: dict[int, Niche | None] = {}
    for lead_id in ids:
        lead = leads.get(lead_id)
        if lead is None:
            result.skip(lead_id, "Lead not found")
            continue
        try:
            if payload.action == "set_status":
                assert payload.status is not None  # noqa: S101 - checked by the schema
                lead.status = validate_user_status_change(lead.status, payload.status)
            elif payload.action == "delete":
                delete_lead(db, lead)
            elif payload.action == "rescore":
                if lead.niche_id not in niches:
                    niches[lead.niche_id] = db.get(Niche, lead.niche_id)
                niche = niches[lead.niche_id]
                if niche is None:
                    result.skip(lead_id, "Niche not found")
                    continue
                apply_score_result(lead, score_lead(lead, niche))
        except AppError as exc:
            result.fail(lead_id, exc.detail)
            continue
        result.ok(lead_id)
    db.flush()


def run_bulk_action(db: Session, ctx: WorkspaceContext, payload: LeadBulkRequest) -> BulkResult:
    ids = list(dict.fromkeys(payload.lead_ids))
    if payload.action == "add_to_campaign":
        assert payload.campaign_id is not None  # noqa: S101 - checked by the schema
        result: BulkResult = add_leads_to_campaign(db, ctx, payload.campaign_id, ids)["bulk"]
    else:
        result = BulkResult()
        if payload.action == "enrich":
            _enrich(db, ctx, ids, result)
        else:
            _per_lead(db, ctx, payload, ids, result)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        f"lead.bulk_{payload.action}",
        "lead",
        None,
        {
            "succeeded": result.succeeded,
            "failed": result.failed,
            "skipped": result.skipped,
            **({"campaign_id": payload.campaign_id} if payload.campaign_id else {}),
            **({"status": str(payload.status)} if payload.status else {}),
        },
    )
    db.commit()
    return result


def lead_stats(db: Session, workspace_id: int, *, niche_id: int | None = None) -> LeadStats:
    conditions = [Lead.workspace_id == workspace_id]
    if niche_id is not None:
        conditions.append(Lead.niche_id == niche_id)
    by_status = {
        str(status): count
        for status, count in db.execute(
            select(Lead.status, func.count(Lead.id)).where(*conditions).group_by(Lead.status),
        ).all()
    }
    total = sum(by_status.values())
    with_email = (
        db.scalar(
            select(func.count(func.distinct(Lead.id)))
            .select_from(Lead)
            .join(EmailContact, EmailContact.lead_id == Lead.id)
            .where(*conditions, EmailContact.opted_out.is_(False)),
        )
        or 0
    )
    average = db.scalar(select(func.avg(Lead.score)).where(*conditions)) or 0.0
    week_ago = datetime.now(UTC) - timedelta(days=7)
    recent = db.scalar(select(func.count(Lead.id)).where(*conditions, Lead.created_at >= week_ago))
    in_sequences = db.scalar(
        select(func.count(func.distinct(CampaignEnrollment.lead_id)))
        .join(Lead, Lead.id == CampaignEnrollment.lead_id)
        .where(*conditions, CampaignEnrollment.status == EnrollmentStatus.ACTIVE),
    )
    return LeadStats(
        total=total,
        by_status=by_status,
        with_email=with_email,
        without_email=max(0, total - with_email),
        average_score=round(float(average), 1),
        added_last_7_days=recent or 0,
        in_active_sequences=in_sequences or 0,
    )
