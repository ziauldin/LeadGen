import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.services.compliance.outreach import (
    primary_recipient_email,
    validate_lead_for_outreach,
)
from app.services.email_generation.personalisation import build_context, render_template
from app.services.email_generation.templates import get_template
from app.services.workspaces.service import get_or_create_settings

OPT_OUT_MARKERS = (
    "not relevant",
    "opt out",
    "unsubscribe",
    "will not contact you again",
)


@dataclass
class RenderedEmail:
    subject: str
    body: str
    recipient_email: str
    template_id: str
    variables: dict[str, str]
    has_opt_out_line: bool
    compliance_errors: list[str]


def has_opt_out_line(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in OPT_OUT_MARKERS)


def load_lead(db: Session, lead_id: int, workspace_id: int) -> Lead:
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
        .options(
            selectinload(Lead.company),
            selectinload(Lead.email_contacts),
            selectinload(Lead.niche),
        ),
    )
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _api_base_url() -> str:
    return settings.api_public_url.rstrip("/")


def render_email_for_lead(
    db: Session,
    lead_id: int,
    workspace_id: int,
    *,
    sender_fallback_name: str,
    template_id: str = "wellpredict",
    unsubscribe_token: str | None = None,
) -> RenderedEmail:
    lead = load_lead(db, lead_id, workspace_id)
    niche = lead.niche or db.get(Niche, lead.niche_id)
    if niche is None:
        raise NotFoundError("Niche not found")
    workspace_settings = get_or_create_settings(db, workspace_id)

    compliance_errors = validate_lead_for_outreach(lead, db)
    recipient = primary_recipient_email(lead)
    if recipient is None and "Lead has no active email contact" not in compliance_errors:
        compliance_errors.append("Lead has no active email contact")

    template = get_template(template_id)
    context = build_context(
        lead,
        niche,
        workspace_settings,
        sender_fallback_name=sender_fallback_name,
        api_base_url=_api_base_url(),
        unsubscribe_token=unsubscribe_token,
    )
    subject = render_template(template.subject, context)
    body = render_template(template.body, context)

    return RenderedEmail(
        subject=subject,
        body=body,
        recipient_email=recipient or "",
        template_id=template_id,
        variables=context.__dict__,
        has_opt_out_line=has_opt_out_line(body),
        compliance_errors=compliance_errors,
    )


def generate_email_message(
    db: Session,
    lead_id: int,
    workspace_id: int,
    *,
    sender_fallback_name: str,
    template_id: str = "wellpredict",
    campaign_id: int | None = None,
) -> EmailMessage:
    if campaign_id is not None:
        campaign = db.scalar(
            select(Campaign.id).where(
                Campaign.id == campaign_id,
                Campaign.workspace_id == workspace_id,
            ),
        )
        if campaign is None:
            raise NotFoundError("Campaign not found")

    token = secrets.token_urlsafe(32)
    rendered = render_email_for_lead(
        db,
        lead_id,
        workspace_id,
        sender_fallback_name=sender_fallback_name,
        template_id=template_id,
        unsubscribe_token=token,
    )
    if rendered.compliance_errors:
        raise ValidationFailedError("; ".join(rendered.compliance_errors))
    if not rendered.has_opt_out_line:
        raise ValidationFailedError("Generated email is missing a required opt-out line")

    message = EmailMessage(
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
        recipient_email=rendered.recipient_email,
        subject=rendered.subject,
        body=rendered.body,
        status=EmailMessageStatus.DRAFT,
        unsubscribe_token=token,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def approve_email_message(db: Session, message_id: int, workspace_id: int) -> EmailMessage:
    message = db.scalar(
        select(EmailMessage)
        .where(EmailMessage.id == message_id, EmailMessage.workspace_id == workspace_id)
        .options(selectinload(EmailMessage.lead).selectinload(Lead.email_contacts)),
    )
    if message is None:
        raise NotFoundError("Email message not found")

    if message.status not in {EmailMessageStatus.DRAFT, EmailMessageStatus.PENDING_APPROVAL}:
        raise ValidationFailedError("Only draft emails can be approved")

    lead = message.lead
    if lead is None:
        raise NotFoundError("Lead not found for email message")

    compliance_errors = validate_lead_for_outreach(lead, db)
    if compliance_errors:
        raise ValidationFailedError("; ".join(compliance_errors))

    if not has_opt_out_line(message.body):
        raise ValidationFailedError("Email is missing a required opt-out line")

    message.status = EmailMessageStatus.APPROVED
    db.commit()
    db.refresh(message)
    return message
