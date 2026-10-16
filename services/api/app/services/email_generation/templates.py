"""Email templates: neutral system templates in code, plus each workspace's own templates.

Template ids are strings: ``system:<slug>`` for built-ins and the numeric id for workspace
templates. The old built-in ids ``wellpredict`` and ``default`` resolve to ``system:intro``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.email_template import EmailTemplateRecord
from app.services.email_generation.personalisation import PersonalisationContext


@dataclass(frozen=True)
class EmailTemplate:
    id: str
    name: str
    subject: str
    body: str
    description: str = ""
    is_system: bool = True


OPT_OUT_FOOTER = """If this is not relevant, reply "not relevant" and I will not contact you again.

To opt out of future emails, use this link: {{unsubscribe_link}}"""

SYSTEM_TEMPLATES: tuple[EmailTemplate, ...] = (
    EmailTemplate(
        id="system:intro",
        name="Introduction",
        description="A short, plain first email that asks for a brief conversation.",
        subject="Quick question about {{company}}",
        body=f"""Hi {{{{first_name}}}},

I came across {{{{company}}}} while researching teams in {{{{industry}}}}. I work with \
organisations on {{{{pain_point}}}}, and thought it might be relevant to you as {{{{role}}}}.

I'm getting in touch from {{{{sender_company}}}}. Would a short conversation be worthwhile to \
see whether what we do could help?

Regards,
{{{{sender_name}}}}

{OPT_OUT_FOOTER}""",
    ),
    EmailTemplate(
        id="system:follow-up",
        name="Gentle follow-up",
        description="A brief nudge for a later step in a sequence.",
        subject="Re: Quick question about {{company}}",
        body=f"""Hi {{{{first_name}}}},

Following up on my note in case it got buried. If {{{{pain_point}}}} is on your list this \
year, I'd be glad to share how other {{{{industry}}}} teams approach it.

If the timing isn't right, no problem at all.

Regards,
{{{{sender_name}}}}

{OPT_OUT_FOOTER}""",
    ),
)
SYSTEM_BY_ID = {template.id: template for template in SYSTEM_TEMPLATES}
LEGACY_ALIASES = {"wellpredict": "system:intro", "default": "system:intro"}
DEFAULT_TEMPLATE_ID = "system:intro"

VARIABLES: tuple[str, ...] = tuple(field.name for field in fields(PersonalisationContext))
_VARIABLE = re.compile(r"{{\s*([^{}]*?)\s*}}")
MAX_SUBJECT = 200
MAX_BODY = 10_000


def canonical_id(template_id: str | None) -> str:
    value = (template_id or DEFAULT_TEMPLATE_ID).strip()
    return LEGACY_ALIASES.get(value, value)


def _from_record(record: EmailTemplateRecord) -> EmailTemplate:
    return EmailTemplate(
        id=str(record.id),
        name=record.name,
        subject=record.subject,
        body=record.body,
        description=record.description or "",
        is_system=False,
    )


def get_template(
    template_id: str | None,
    db: Session | None = None,
    workspace_id: int | None = None,
) -> EmailTemplate:
    """Resolve a template id. Raises ``KeyError`` when it does not exist for this workspace."""
    key = canonical_id(template_id)
    if key in SYSTEM_BY_ID:
        return SYSTEM_BY_ID[key]
    if db is not None and workspace_id is not None and key.isdigit():
        record = db.scalar(
            select(EmailTemplateRecord).where(
                EmailTemplateRecord.id == int(key),
                EmailTemplateRecord.workspace_id == workspace_id,
            ),
        )
        if record is not None:
            return _from_record(record)
    raise KeyError(f"Unknown template: {template_id}")


def list_templates(
    db: Session | None = None,
    workspace_id: int | None = None,
    *,
    include_archived: bool = False,
) -> list[EmailTemplate]:
    templates = list(SYSTEM_TEMPLATES)
    if db is not None and workspace_id is not None:
        query = select(EmailTemplateRecord).where(EmailTemplateRecord.workspace_id == workspace_id)
        if not include_archived:
            query = query.where(EmailTemplateRecord.is_archived.is_(False))
        records = db.scalars(query.order_by(EmailTemplateRecord.name)).all()
        templates.extend(_from_record(record) for record in records)
    return templates


def template_problems(subject: str, body: str) -> list[str]:
    """Problems that stop a template being saved: unknown variables, missing opt-out link."""
    problems: list[str] = []
    unknown = sorted(
        {name for name in _VARIABLE.findall(f"{subject}\n{body}") if name not in VARIABLES},
    )
    if unknown:
        allowed = ", ".join(VARIABLES)
        problems.append(f"Unknown variables: {', '.join(unknown)}. Allowed: {allowed}")
    if "{{unsubscribe_link}}" not in body.replace(" ", ""):
        problems.append("The body must include {{unsubscribe_link}} so recipients can opt out")
    if not subject.strip() or len(subject) > MAX_SUBJECT:
        problems.append(f"The subject must be 1-{MAX_SUBJECT} characters")
    if not body.strip() or len(body) > MAX_BODY:
        problems.append(f"The body must be 1-{MAX_BODY} characters")
    return problems


def _get_record(db: Session, workspace_id: int, template_id: int) -> EmailTemplateRecord:
    record = db.scalar(
        select(EmailTemplateRecord).where(
            EmailTemplateRecord.id == template_id,
            EmailTemplateRecord.workspace_id == workspace_id,
        ),
    )
    if record is None:
        raise NotFoundError("Template not found")
    return record


def create_template(
    db: Session,
    workspace_id: int,
    *,
    name: str,
    subject: str,
    body: str,
    description: str | None = None,
    created_by: int | None = None,
) -> EmailTemplateRecord:
    problems = template_problems(subject, body)
    if problems:
        raise ValidationFailedError("; ".join(problems))
    record = EmailTemplateRecord(
        workspace_id=workspace_id,
        name=name.strip(),
        subject=subject,
        body=body,
        description=description,
        created_by=created_by,
    )
    db.add(record)
    db.flush()
    return record


def update_template(
    db: Session,
    workspace_id: int,
    template_id: int,
    updates: dict,
) -> EmailTemplateRecord:
    record = _get_record(db, workspace_id, template_id)
    subject = updates.get("subject", record.subject)
    body = updates.get("body", record.body)
    problems = template_problems(subject, body)
    if problems:
        raise ValidationFailedError("; ".join(problems))
    for field_name in ("name", "subject", "body", "description", "is_archived"):
        if field_name in updates and updates[field_name] is not None:
            setattr(record, field_name, updates[field_name])
    db.flush()
    return record


def archive_template(db: Session, workspace_id: int, template_id: int) -> EmailTemplateRecord:
    record = _get_record(db, workspace_id, template_id)
    record.is_archived = True
    db.flush()
    return record
