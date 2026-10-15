from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.tenancy import WorkspaceContext
from app.models.email_template import EmailTemplateRecord
from app.schemas.template import TemplateCreate, TemplateRead, TemplateUpdate, TemplateVariables
from app.services.email_generation.templates import (
    VARIABLES,
    EmailTemplate,
    archive_template,
    create_template,
    get_template,
    list_templates,
    update_template,
)
from app.services.workspaces.service import audit

router = APIRouter(prefix="/templates", tags=["templates"])


def _read(template: EmailTemplate | EmailTemplateRecord) -> TemplateRead:
    if isinstance(template, EmailTemplateRecord):
        return TemplateRead(
            id=str(template.id),
            name=template.name,
            description=template.description or "",
            subject=template.subject,
            body=template.body,
            is_system=False,
            is_archived=template.is_archived,
        )
    return TemplateRead(
        id=template.id,
        name=template.name,
        description=template.description,
        subject=template.subject,
        body=template.body,
        is_system=template.is_system,
    )


@router.get("", response_model=list[TemplateRead])
def list_email_templates(
    include_archived: bool = Query(default=False),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[TemplateRead]:
    templates = [_read(template) for template in list_templates(db, ctx.workspace_id)]
    if include_archived:
        archived = db.scalars(
            select(EmailTemplateRecord).where(
                EmailTemplateRecord.workspace_id == ctx.workspace_id,
                EmailTemplateRecord.is_archived.is_(True),
            ),
        ).all()
        templates.extend(_read(record) for record in archived)
    return templates


@router.get("/variables", response_model=TemplateVariables)
def template_variables(
    _ctx: WorkspaceContext = Depends(get_current_workspace),
) -> TemplateVariables:
    return TemplateVariables(variables=list(VARIABLES), required=["unsubscribe_link"])


@router.get("/{template_id}", response_model=TemplateRead)
def get_email_template(
    template_id: str,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> TemplateRead:
    try:
        return _read(get_template(template_id, db, ctx.workspace_id))
    except KeyError as exc:
        raise NotFoundError("Template not found") from exc


@router.post("", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def create_email_template(
    payload: TemplateCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> TemplateRead:
    record = create_template(
        db,
        ctx.workspace_id,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        description=payload.description,
        created_by=ctx.user_id,
    )
    audit(db, ctx.workspace_id, ctx.user_id, "template.created", "email_template", record.id)
    db.commit()
    db.refresh(record)
    return _read(record)


def _record_id(template_id: str) -> int:
    if not template_id.isdigit():
        raise NotFoundError("System templates can't be changed; copy one instead")
    return int(template_id)


@router.patch("/{template_id}", response_model=TemplateRead)
def update_email_template(
    template_id: str,
    payload: TemplateUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> TemplateRead:
    record = update_template(
        db,
        ctx.workspace_id,
        _record_id(template_id),
        payload.model_dump(exclude_unset=True),
    )
    audit(db, ctx.workspace_id, ctx.user_id, "template.updated", "email_template", record.id)
    db.commit()
    db.refresh(record)
    return _read(record)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_template(
    template_id: str,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    """Archive the template. Campaign steps keep their own copy of its text."""
    record = archive_template(db, ctx.workspace_id, _record_id(template_id))
    audit(db, ctx.workspace_id, ctx.user_id, "template.archived", "email_template", record.id)
    db.commit()
