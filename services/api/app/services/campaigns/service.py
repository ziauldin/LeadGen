from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign, CampaignStep
from app.models.enrollment import CampaignEnrollment
from app.models.enums import CampaignStatus, LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.schemas.common import BulkResult
from app.services.billing.usage import check_campaign_limit
from app.services.campaigns.sequences import StepRenderError, enroll_lead
from app.services.email_generation.templates import DEFAULT_TEMPLATE_ID, get_template
from app.services.workspaces.service import get_or_create_settings


def _ensure_sending_credential(db: Session, workspace_id: int, credential_id: int) -> None:
    from app.models.enums import ProviderType
    from app.models.provider_credential import ProviderCredential

    found = db.scalar(
        select(ProviderCredential.id).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider_type == ProviderType.EMAIL,
        ),
    )
    if found is None:
        raise NotFoundError("Sending account not found")


NOT_NULL_FIELDS = {"name", "daily_send_limit", "stop_on_reply"}


def update_campaign(db: Session, campaign: Campaign, updates: dict) -> Campaign:
    updates = dict(updates)
    steps = updates.pop("steps", None)
    if updates.get("sender_credential_id") is not None:
        _ensure_sending_credential(db, campaign.workspace_id, updates["sender_credential_id"])
    for field, value in updates.items():
        if value is None and field in NOT_NULL_FIELDS:
            continue
        setattr(campaign, field, value)
    if steps is not None:
        replace_steps(db, campaign, steps)
    db.commit()
    db.refresh(campaign)
    return campaign


def replace_steps(db: Session, campaign: Campaign, steps: list[dict]) -> None:
    """Make the campaign's steps match ``steps``. Steps that already have emails stay."""
    from app.models.email_message import EmailMessage

    resolved = {
        step["step_number"]: _resolve_step_content(db, campaign.workspace_id, step)
        for step in steps
    }
    existing = {step.step_number: step for step in campaign.steps}
    for number, step in existing.items():
        if number in resolved:
            continue
        used = db.scalar(
            select(EmailMessage.id).where(EmailMessage.campaign_step_id == step.id).limit(1),
        )
        if used is not None:
            raise ValidationFailedError(
                f"Step {number} already has emails, so it can't be removed",
            )
        campaign.steps.remove(step)
        db.delete(step)
    fields = (
        "delay_days",
        "subject_template",
        "body_template",
        "template_id",
        "use_ai",
        "ai_instructions",
        "thread_with_previous",
    )
    for number, data in sorted(resolved.items()):
        step = existing.get(number)
        if step is None:
            step = CampaignStep(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                step_number=number,
            )
            campaign.steps.append(step)
        for field in fields:
            if field in data:
                setattr(step, field, data[field])
    db.flush()


def get_campaign(db: Session, campaign_id: int, workspace_id: int) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
        .options(selectinload(Campaign.steps)),
    )
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


def _resolve_step_content(db: Session, workspace_id: int, step: dict) -> dict:
    """Copy a saved template's text into the step, so later template edits don't change it."""
    step = dict(step)
    template_id = step.get("template_id")
    if template_id:
        try:
            template = get_template(template_id, db, workspace_id)
        except KeyError as exc:
            raise ValidationFailedError(f"Unknown template: {template_id}") from exc
        step["template_id"] = template.id
        step["subject_template"] = step.get("subject_template") or template.subject
        step["body_template"] = step.get("body_template") or template.body
    return step


def create_campaign(
    db: Session,
    ctx: WorkspaceContext,
    niche_id: int,
    name: str,
    steps: list[dict],
    daily_send_limit: int | None = None,
    sending_window_start: str | None = None,
    sending_window_end: str | None = None,
    schedule: dict | None = None,
) -> Campaign:
    niche = db.scalar(
        select(Niche).where(Niche.id == niche_id, Niche.workspace_id == ctx.workspace_id),
    )
    if niche is None:
        raise NotFoundError("Niche not found")
    check_campaign_limit(db, ctx.workspace)

    if not steps:
        steps = [{"step_number": 1, "delay_days": 0, "template_id": DEFAULT_TEMPLATE_ID}]
    steps = [_resolve_step_content(db, ctx.workspace_id, step) for step in steps]

    campaign = Campaign(
        workspace_id=ctx.workspace_id,
        niche_id=niche_id,
        name=name.strip(),
        status=CampaignStatus.DRAFT,
        daily_send_limit=daily_send_limit or settings.default_daily_send_limit,
        sending_window_start=sending_window_start or settings.default_sending_window_start,
        sending_window_end=sending_window_end or settings.default_sending_window_end,
    )
    for field, value in (schedule or {}).items():
        if value is not None:
            setattr(campaign, field, value)
    if campaign.sender_credential_id is not None:
        _ensure_sending_credential(db, ctx.workspace_id, campaign.sender_credential_id)
    db.add(campaign)
    db.flush()

    for step in steps:
        db.add(
            CampaignStep(
                workspace_id=ctx.workspace_id,
                campaign_id=campaign.id,
                step_number=step["step_number"],
                delay_days=step.get("delay_days", 0),
                subject_template=step["subject_template"],
                body_template=step["body_template"],
                template_id=step.get("template_id"),
                use_ai=bool(step.get("use_ai")),
                ai_instructions=step.get("ai_instructions"),
                thread_with_previous=step.get("thread_with_previous", True),
            ),
        )

    db.commit()
    db.refresh(campaign)
    return campaign


def add_leads_to_campaign(
    db: Session,
    ctx: WorkspaceContext,
    campaign_id: int,
    lead_ids: list[int],
) -> dict:
    """Enroll leads and create each one's step-1 draft. Ineligible leads are reported."""
    campaign = get_campaign(db, campaign_id, ctx.workspace_id)
    if not campaign.steps:
        raise ValidationFailedError("Campaign has no steps configured")

    actor = db.get(User, ctx.user_id)
    workspace_settings = get_or_create_settings(db, ctx.workspace_id)
    sender_fallback = workspace_settings.sender_name or (actor.name if actor else "The team")

    created = 0
    skipped = 0
    errors: list[str] = []
    message_ids: list[int] = []
    bulk = BulkResult()

    for lead_id in dict.fromkeys(lead_ids):
        lead = db.scalar(
            select(Lead)
            .where(
                Lead.id == lead_id,
                Lead.niche_id == campaign.niche_id,
                Lead.workspace_id == ctx.workspace_id,
            )
            .options(selectinload(Lead.email_contacts), selectinload(Lead.company)),
        )
        if lead is None:
            errors.append(f"Lead {lead_id} not found in campaign niche")
            bulk.skip(lead_id, "Not found in the campaign's niche")
            skipped += 1
            continue
        if lead.status in {LeadStatus.DISQUALIFIED, LeadStatus.OPTED_OUT}:
            errors.append(f"Lead {lead_id}: lead is {lead.status}")
            bulk.skip(lead_id, f"Lead is {lead.status}")
            skipped += 1
            continue
        already = db.scalar(
            select(CampaignEnrollment.id).where(
                CampaignEnrollment.campaign_id == campaign.id,
                CampaignEnrollment.lead_id == lead.id,
            ),
        )
        if already:
            bulk.skip(lead_id, "Already in this campaign")
            skipped += 1
            continue

        try:
            message = enroll_lead(
                db,
                campaign=campaign,
                lead=lead,
                sender_fallback_name=sender_fallback,
            )
        except StepRenderError as exc:
            errors.append(f"Lead {lead_id}: {exc}")
            bulk.fail(lead_id, str(exc))
            skipped += 1
            continue
        message_ids.append(message.id)
        bulk.ok(lead_id, f"Draft {message.id} created")
        created += 1

    db.commit()
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "message_ids": message_ids,
        "bulk": bulk,
    }


def start_campaign(db: Session, campaign_id: int, workspace_id: int) -> Campaign:
    campaign = get_campaign(db, campaign_id, workspace_id)
    if not campaign.steps:
        raise ValidationFailedError("Campaign must have at least one step")
    campaign.status = CampaignStatus.ACTIVE
    db.commit()
    db.refresh(campaign)
    return campaign


def pause_campaign(db: Session, campaign_id: int, workspace_id: int) -> Campaign:
    campaign = get_campaign(db, campaign_id, workspace_id)
    campaign.status = CampaignStatus.PAUSED
    db.commit()
    db.refresh(campaign)
    return campaign
