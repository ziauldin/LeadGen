import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.compliance.outreach import (
    primary_recipient_email,
    validate_lead_for_outreach,
)
from app.services.email_generation.personalisation import build_context, render_template
from app.services.email_generation.templates import get_template

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


def _load_lead_context(db: Session, lead_id: int, user_id: int) -> tuple[Lead, Niche, UserSettings | None]:
    lead = db.scalar(
        select(Lead)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Lead.id == lead_id, Niche.user_id == user_id)
        .options(
            selectinload(Lead.company),
            selectinload(Lead.email_contacts),
            selectinload(Lead.niche),
        ),
    )
    if lead is None:
        raise ValueError("Lead not found")

    niche = lead.niche or db.get(Niche, lead.niche_id)
    if niche is None:
        raise ValueError("Niche not found")

    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    user_settings = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    return lead, niche, user_settings


def _api_base_url() -> str:
    return settings.api_public_url.rstrip("/")


def render_email_for_lead(
    db: Session,
    lead_id: int,
    user_id: int,
    template_id: str = "wellpredict",
    unsubscribe_token: str | None = None,
) -> RenderedEmail:
    lead, niche, user_settings = _load_lead_context(db, lead_id, user_id)
    user = db.get(User, user_id)
    assert user is not None

    compliance_errors = validate_lead_for_outreach(lead, db)
    recipient = primary_recipient_email(lead)
    if recipient is None:
        compliance_errors.append("Lead has no active email contact")

    template = get_template(template_id)
    context = build_context(
        lead,
        niche,
        user,
        user_settings,
        api_base_url=_api_base_url(),
        unsubscribe_token=unsubscribe_token,
    )
    subject = render_template(template.subject, context)
    body = render_template(template.body, context)
    body_lower = body.lower()
    has_opt_out = any(marker in body_lower for marker in OPT_OUT_MARKERS)

    return RenderedEmail(
        subject=subject,
        body=body,
        recipient_email=recipient or "",
        template_id=template_id,
        variables=context.__dict__,
        has_opt_out_line=has_opt_out,
        compliance_errors=compliance_errors,
    )


def generate_email_message(
    db: Session,
    lead_id: int,
    user_id: int,
    template_id: str = "wellpredict",
    campaign_id: int | None = None,
) -> EmailMessage:
    rendered = render_email_for_lead(db, lead_id, user_id, template_id=template_id)
    if rendered.compliance_errors:
        raise ValueError("; ".join(rendered.compliance_errors))
    if not rendered.has_opt_out_line:
        raise ValueError("Generated email is missing a required opt-out line")

    token = secrets.token_urlsafe(32)
    final_render = render_email_for_lead(
        db,
        lead_id,
        user_id,
        template_id=template_id,
        unsubscribe_token=token,
    )

    message = EmailMessage(
        campaign_id=campaign_id,
        lead_id=lead_id,
        recipient_email=final_render.recipient_email,
        subject=final_render.subject,
        body=final_render.body,
        status=EmailMessageStatus.DRAFT,
        unsubscribe_token=token,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def approve_email_message(db: Session, message_id: int, user_id: int) -> EmailMessage:
    message = db.scalar(
        select(EmailMessage)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(EmailMessage.id == message_id, Niche.user_id == user_id)
        .options(selectinload(EmailMessage.lead).selectinload(Lead.email_contacts)),
    )
    if message is None:
        raise ValueError("Email message not found")

    if message.status not in {EmailMessageStatus.DRAFT, EmailMessageStatus.PENDING_APPROVAL}:
        raise ValueError("Only draft emails can be approved")

    lead = message.lead
    if lead is None:
        raise ValueError("Lead not found for email message")

    compliance_errors = validate_lead_for_outreach(lead, db)
    if compliance_errors:
        raise ValueError("; ".join(compliance_errors))

    if not any(marker in message.body.lower() for marker in OPT_OUT_MARKERS):
        raise ValueError("Email is missing a required opt-out line")

    message.status = EmailMessageStatus.APPROVED
    db.commit()
    db.refresh(message)
    return message
