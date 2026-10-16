import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, QuotaExceededError, ValidationFailedError
from app.core.flags import feature_enabled
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.compliance.outreach import (
    primary_recipient_email,
    validate_lead_for_outreach,
)
from app.services.email_generation.ai_writer import PROMPT_VERSION, AIWriteError, write_email
from app.services.email_generation.personalisation import (
    PersonalisationContext,
    build_context,
    render_template,
)
from app.services.email_generation.templates import (
    DEFAULT_TEMPLATE_ID,
    OPT_OUT_FOOTER,
    EmailTemplate,
    canonical_id,
    get_template,
)
from app.services.llm.base import LLMError
from app.services.llm.factory import resolve_llm, take_pending_usage
from app.services.sending.state import transition
from app.services.workspaces.service import audit, get_or_create_settings

GenerationMode = Literal["template", "ai"]
EDITABLE_STATES = {EmailMessageStatus.DRAFT, EmailMessageStatus.PENDING_APPROVAL}

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
    generation_mode: str = "template"
    llm_model: str | None = None
    prompt_version: str | None = None
    generation_note: str | None = None


@dataclass
class EmailContent:
    subject: str
    body: str
    template_id: str
    generation_mode: str  # template | ai | template_fallback
    variables: dict[str, str] = field(default_factory=dict)
    llm_model: str | None = None
    prompt_version: str | None = None
    note: str | None = None


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


def ai_disabled_reason(workspace_settings: WorkspaceSettings | None) -> str | None:
    workspace = workspace_settings.workspace if workspace_settings is not None else None
    if not feature_enabled("ai_emails", workspace):
        return "AI writing is not enabled on this server"
    if workspace_settings is None or workspace_settings.ai_mode == "off":
        return "AI writing is turned off in workspace settings"
    return None


def _ai_body(draft_body: str, context: PersonalisationContext) -> str:
    footer = render_template(OPT_OUT_FOOTER, context)
    return f"{draft_body.strip()}\n\nRegards,\n{context.sender_name}\n\n{footer}"


def build_content(
    db: Session,
    *,
    workspace_id: int,
    lead: Lead,
    niche: Niche,
    sender_fallback_name: str,
    unsubscribe_token: str | None,
    template_id: str | None = None,
    mode: GenerationMode = "template",
    instructions: str | None = None,
    step_number: int = 1,
    previous_subject: str | None = None,
    user_id: int | None = None,
    strict_ai: bool = False,
    subject_template: str | None = None,
    body_template: str | None = None,
) -> EmailContent:
    """Produce subject and body for one lead from a template or, if asked, the LLM.

    AI drafts that can't be produced (no provider, quota, guardrails) fall back to the
    template and say why in ``note``. With ``strict_ai`` a disabled AI setting is an error
    instead, so a person who explicitly asked for AI is told why it isn't available.
    ``subject_template``/``body_template`` (a campaign step's own text) replace the template's.
    """
    take_pending_usage(db)  # usage from an earlier, abandoned draft stays unlinked
    workspace_settings = get_or_create_settings(db, workspace_id)
    if subject_template and body_template:
        template = EmailTemplate(
            id=canonical_id(template_id) if template_id else "custom",
            name="Campaign step",
            subject=subject_template,
            body=body_template,
            is_system=False,
        )
    else:
        template = get_template(template_id or DEFAULT_TEMPLATE_ID, db, workspace_id)
    context = build_context(
        lead,
        niche,
        workspace_settings,
        sender_fallback_name=sender_fallback_name,
        api_base_url=_api_base_url(),
        unsubscribe_token=unsubscribe_token,
    )

    note: str | None = None
    if mode == "ai":
        disabled = ai_disabled_reason(workspace_settings)
        resolved = None if disabled else resolve_llm(db, workspace_id)
        if disabled is None and resolved is None:
            disabled = "No AI provider is configured; add an LLM key in Settings"
        if disabled and strict_ai:
            raise ValidationFailedError(disabled)
        workspace = db.get(Workspace, workspace_id)
        if disabled or workspace is None:
            note = f"Used the template: {disabled}"
        else:
            try:
                draft = write_email(
                    db,
                    workspace,
                    lead=lead,
                    niche=niche,
                    workspace_settings=workspace_settings,
                    sender_name=context.sender_name,
                    step_number=step_number,
                    previous_subject=previous_subject,
                    instructions=instructions,
                    user_id=user_id,
                    resolved=resolved,
                )
            except QuotaExceededError:
                note = "Used the template: the AI token allowance for this month is used up"
            except (AIWriteError, LLMError) as exc:
                note = f"Used the template: {str(exc)[:400]}"
            else:
                return EmailContent(
                    subject=draft.subject,
                    body=_ai_body(draft.body, context),
                    template_id=template.id,
                    generation_mode="ai",
                    variables=context.__dict__,
                    llm_model=draft.model,
                    prompt_version=PROMPT_VERSION,
                )

    return EmailContent(
        subject=render_template(template.subject, context),
        body=render_template(template.body, context),
        template_id=template.id,
        generation_mode="template_fallback" if note else "template",
        variables=context.__dict__,
        note=note,
    )


def _compliance_errors(db: Session, lead: Lead) -> tuple[str | None, list[str]]:
    errors = validate_lead_for_outreach(lead, db)
    recipient = primary_recipient_email(lead)
    if recipient is None and "Lead has no active email contact" not in errors:
        errors.append("Lead has no active email contact")
    return recipient, errors


def _niche_for(db: Session, lead: Lead) -> Niche:
    niche = lead.niche or db.get(Niche, lead.niche_id)
    if niche is None:
        raise NotFoundError("Niche not found")
    return niche


def render_email_for_lead(
    db: Session,
    lead_id: int,
    workspace_id: int,
    *,
    sender_fallback_name: str,
    template_id: str = DEFAULT_TEMPLATE_ID,
    unsubscribe_token: str | None = None,
    mode: GenerationMode = "template",
    instructions: str | None = None,
    user_id: int | None = None,
) -> RenderedEmail:
    lead = load_lead(db, lead_id, workspace_id)
    niche = _niche_for(db, lead)
    recipient, compliance_errors = _compliance_errors(db, lead)
    content = build_content(
        db,
        workspace_id=workspace_id,
        lead=lead,
        niche=niche,
        sender_fallback_name=sender_fallback_name,
        unsubscribe_token=unsubscribe_token,
        template_id=template_id,
        mode=mode,
        instructions=instructions,
        user_id=user_id,
        strict_ai=True,
    )
    return RenderedEmail(
        subject=content.subject,
        body=content.body,
        recipient_email=recipient or "",
        template_id=content.template_id,
        variables=content.variables,
        has_opt_out_line=has_opt_out_line(content.body),
        compliance_errors=compliance_errors,
        generation_mode=content.generation_mode,
        llm_model=content.llm_model,
        prompt_version=content.prompt_version,
        generation_note=content.note,
    )


def apply_content(message: EmailMessage, content: EmailContent) -> None:
    message.subject = content.subject
    message.body = content.body
    message.generation_mode = content.generation_mode
    message.template_id = content.template_id
    message.llm_model = content.llm_model
    message.prompt_version = content.prompt_version
    message.generation_note = content.note


def link_llm_usage(db: Session, message: EmailMessage) -> None:
    """Attach the usage rows written while drafting this message to it."""
    for row in take_pending_usage(db):
        if row.purpose == "email_draft" and row.workspace_id == message.workspace_id:
            row.email_message_id = message.id


def generate_email_message(
    db: Session,
    lead_id: int,
    workspace_id: int,
    *,
    sender_fallback_name: str,
    template_id: str = DEFAULT_TEMPLATE_ID,
    campaign_id: int | None = None,
    mode: GenerationMode = "template",
    instructions: str | None = None,
    user_id: int | None = None,
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

    lead = load_lead(db, lead_id, workspace_id)
    recipient, compliance_errors = _compliance_errors(db, lead)
    if compliance_errors:
        raise ValidationFailedError("; ".join(compliance_errors))

    token = secrets.token_urlsafe(32)
    content = build_content(
        db,
        workspace_id=workspace_id,
        lead=lead,
        niche=_niche_for(db, lead),
        sender_fallback_name=sender_fallback_name,
        unsubscribe_token=token,
        template_id=template_id,
        mode=mode,
        instructions=instructions,
        user_id=user_id,
        strict_ai=True,
    )
    if not has_opt_out_line(content.body):
        raise ValidationFailedError("Generated email is missing a required opt-out line")

    recipient = recipient or ""
    message = EmailMessage(
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
        recipient_email=recipient,
        recipient_domain=recipient.rsplit("@", 1)[-1].lower() or None,
        subject="",
        body="",
        status=EmailMessageStatus.DRAFT,
        unsubscribe_token=token,
    )
    apply_content(message, content)
    db.add(message)
    db.flush()
    link_llm_usage(db, message)
    db.commit()
    db.refresh(message)
    return message


def regenerate_email_message(
    db: Session,
    message_id: int,
    workspace_id: int,
    *,
    sender_fallback_name: str,
    mode: GenerationMode = "template",
    template_id: str | None = None,
    instructions: str | None = None,
    actor_id: int | None = None,
) -> EmailMessage:
    """Rewrite a draft that hasn't been approved yet. Keeps its unsubscribe token and thread."""
    message = db.scalar(
        select(EmailMessage).where(
            EmailMessage.id == message_id,
            EmailMessage.workspace_id == workspace_id,
        ),
    )
    if message is None:
        raise NotFoundError("Email message not found")
    if message.status not in EDITABLE_STATES:
        raise ValidationFailedError("Only drafts waiting for approval can be regenerated")

    lead = load_lead(db, message.lead_id, workspace_id)
    step_number = message.step_number or 1
    threaded_subject = (
        message.subject
        if step_number > 1 and (message.subject or "").lower().startswith("re:")
        else None
    )
    content = build_content(
        db,
        workspace_id=workspace_id,
        lead=lead,
        niche=_niche_for(db, lead),
        sender_fallback_name=sender_fallback_name,
        unsubscribe_token=message.unsubscribe_token,
        template_id=canonical_id(template_id or message.template_id),
        mode=mode,
        instructions=instructions,
        step_number=step_number,
        previous_subject=message.subject if step_number > 1 else None,
        user_id=actor_id,
        strict_ai=True,
    )
    if not has_opt_out_line(content.body):
        raise ValidationFailedError("Generated email is missing a required opt-out line")
    apply_content(message, content)
    if threaded_subject:
        message.subject = threaded_subject
    message.edited_by = None
    message.edited_at = None
    link_llm_usage(db, message)
    audit(
        db,
        workspace_id,
        actor_id,
        "email.regenerated",
        "email_message",
        message.id,
        {"mode": content.generation_mode, "template_id": content.template_id},
    )
    db.commit()
    db.refresh(message)
    return message


def approve_email_message(
    db: Session,
    message_id: int,
    workspace_id: int,
    *,
    actor_id: int | None = None,
) -> EmailMessage:
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

    transition(db, message, EmailMessageStatus.APPROVED, actor_id=actor_id)
    message.approved_by = actor_id
    message.approved_at = datetime.now(UTC)
    message.next_attempt_at = None
    db.commit()
    db.refresh(message)
    return message
