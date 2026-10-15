import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign, CampaignStep
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.models.workspace import WorkspaceSettings
from app.services.billing.usage import check_campaign_limit
from app.services.compliance.outreach import primary_recipient_email, validate_lead_for_outreach
from app.services.email_generation.generator import has_opt_out_line
from app.services.email_generation.personalisation import build_context, render_template
from app.services.email_generation.templates import WELLPREDICT_TEMPLATE
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


def update_campaign(db: Session, campaign: Campaign, updates: dict) -> Campaign:
    if updates.get("sender_credential_id") is not None:
        _ensure_sending_credential(db, campaign.workspace_id, updates["sender_credential_id"])
    for field, value in updates.items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_campaign(db: Session, campaign_id: int, workspace_id: int) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
        .options(selectinload(Campaign.steps)),
    )
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


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
        steps = [
            {
                "step_number": 1,
                "delay_days": 0,
                "subject_template": WELLPREDICT_TEMPLATE.subject,
                "body_template": WELLPREDICT_TEMPLATE.body,
            },
        ]

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
            ),
        )

    db.commit()
    db.refresh(campaign)
    return campaign


def _render_step(
    lead: Lead,
    niche: Niche,
    workspace_settings: WorkspaceSettings,
    sender_fallback_name: str,
    step: CampaignStep,
    unsubscribe_token: str,
) -> tuple[str, str, str]:
    context = build_context(
        lead,
        niche,
        workspace_settings,
        sender_fallback_name=sender_fallback_name,
        api_base_url=settings.api_public_url.rstrip("/"),
        unsubscribe_token=unsubscribe_token,
    )
    subject = render_template(step.subject_template, context)
    body = render_template(step.body_template, context)
    recipient = primary_recipient_email(lead) or ""
    return subject, body, recipient


def add_leads_to_campaign(
    db: Session,
    ctx: WorkspaceContext,
    campaign_id: int,
    lead_ids: list[int],
) -> dict[str, int | list[str] | list[int]]:
    campaign = get_campaign(db, campaign_id, ctx.workspace_id)
    if not campaign.steps:
        raise ValidationFailedError("Campaign has no steps configured")

    first_step = sorted(campaign.steps, key=lambda step: step.step_number)[0]
    niche = db.get(Niche, campaign.niche_id)
    if niche is None:
        raise NotFoundError("Niche not found")
    actor = db.get(User, ctx.user_id)
    sender_fallback = actor.name if actor else "The team"
    workspace_settings = get_or_create_settings(db, ctx.workspace_id)

    created = 0
    skipped = 0
    errors: list[str] = []
    message_ids: list[int] = []

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
            skipped += 1
            continue

        existing = db.scalar(
            select(EmailMessage.id).where(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.lead_id == lead.id,
            ),
        )
        if existing:
            skipped += 1
            continue

        compliance_errors = validate_lead_for_outreach(lead, db)
        if compliance_errors:
            errors.append(f"Lead {lead_id}: {'; '.join(compliance_errors)}")
            skipped += 1
            continue

        token = secrets.token_urlsafe(32)
        subject, body, recipient = _render_step(
            lead,
            niche,
            workspace_settings,
            sender_fallback,
            first_step,
            token,
        )
        if not has_opt_out_line(body):
            errors.append(f"Lead {lead_id}: generated email missing opt-out line")
            skipped += 1
            continue

        message = EmailMessage(
            workspace_id=ctx.workspace_id,
            campaign_id=campaign.id,
            lead_id=lead.id,
            recipient_email=recipient,
            recipient_domain=recipient.rsplit("@", 1)[-1].lower() or None,
            subject=subject,
            body=body,
            status=EmailMessageStatus.DRAFT,
            unsubscribe_token=token,
            generation_mode="template",
        )
        db.add(message)
        db.flush()
        message_ids.append(message.id)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors, "message_ids": message_ids}


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
