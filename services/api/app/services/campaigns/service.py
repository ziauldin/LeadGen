import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.campaign import Campaign, CampaignStep
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.services.compliance.outreach import primary_recipient_email, validate_lead_for_outreach
from app.services.email_generation.generator import OPT_OUT_MARKERS
from app.services.email_generation.personalisation import build_context, render_template
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.email_generation.templates import WELLPREDICT_TEMPLATE


def _get_owned_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .join(Niche, Campaign.niche_id == Niche.id)
        .where(Campaign.id == campaign_id, Niche.user_id == user_id)
        .options(selectinload(Campaign.steps)),
    )
    if campaign is None:
        raise ValueError("Campaign not found")
    return campaign


def create_campaign(
    db: Session,
    user_id: int,
    niche_id: int,
    name: str,
    steps: list[dict],
    daily_send_limit: int | None = None,
    sending_window_start: str | None = None,
    sending_window_end: str | None = None,
) -> Campaign:
    niche = db.scalar(select(Niche).where(Niche.id == niche_id, Niche.user_id == user_id))
    if niche is None:
        raise ValueError("Niche not found")

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
        niche_id=niche_id,
        name=name.strip(),
        status=CampaignStatus.DRAFT,
        daily_send_limit=daily_send_limit or settings.default_daily_send_limit,
        sending_window_start=sending_window_start or settings.default_sending_window_start,
        sending_window_end=sending_window_end or settings.default_sending_window_end,
    )
    db.add(campaign)
    db.flush()

    for step in steps:
        db.add(
            CampaignStep(
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


def _render_campaign_step_email(
    db: Session,
    lead: Lead,
    niche: Niche,
    user: User,
    user_settings: UserSettings | None,
    step: CampaignStep,
    unsubscribe_token: str,
) -> tuple[str, str, str]:
    context = build_context(
        lead,
        niche,
        user,
        user_settings,
        api_base_url=settings.api_public_url.rstrip("/"),
        unsubscribe_token=unsubscribe_token,
    )
    subject = render_template(step.subject_template, context)
    body = render_template(step.body_template, context)
    recipient = primary_recipient_email(lead) or ""
    return subject, body, recipient


def add_leads_to_campaign(
    db: Session,
    campaign_id: int,
    user_id: int,
    lead_ids: list[int],
) -> dict[str, int | list[str] | list[int]]:
    campaign = _get_owned_campaign(db, campaign_id, user_id)
    if not campaign.steps:
        raise ValueError("Campaign has no steps configured")

    first_step = sorted(campaign.steps, key=lambda step: step.step_number)[0]
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    user_settings = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))

    created = 0
    skipped = 0
    errors: list[str] = []
    message_ids: list[int] = []

    for lead_id in lead_ids:
        lead = db.scalar(
            select(Lead)
            .where(Lead.id == lead_id, Lead.niche_id == campaign.niche_id)
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
        niche = db.get(Niche, campaign.niche_id)
        assert niche is not None
        subject, body, recipient = _render_campaign_step_email(
            db,
            lead,
            niche,
            user,
            user_settings,
            first_step,
            token,
        )

        if not any(marker in body.lower() for marker in OPT_OUT_MARKERS):
            errors.append(f"Lead {lead_id}: generated email missing opt-out line")
            skipped += 1
            continue

        message = EmailMessage(
            campaign_id=campaign.id,
            lead_id=lead.id,
            recipient_email=recipient,
            subject=subject,
            body=body,
            status=EmailMessageStatus.DRAFT,
            unsubscribe_token=token,
        )
        db.add(message)
        db.flush()
        message_ids.append(message.id)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors, "message_ids": message_ids}


def start_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    campaign = _get_owned_campaign(db, campaign_id, user_id)
    if not campaign.steps:
        raise ValueError("Campaign must have at least one step")
    campaign.status = CampaignStatus.ACTIVE
    db.commit()
    db.refresh(campaign)
    return campaign


def pause_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    campaign = _get_owned_campaign(db, campaign_id, user_id)
    campaign.status = CampaignStatus.PAUSED
    db.commit()
    db.refresh(campaign)
    return campaign
