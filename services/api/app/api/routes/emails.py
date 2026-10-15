from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace, get_verified_workspace
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.user import User
from app.schemas.email import (
    EmailApproveRequest,
    EmailApproveResponse,
    EmailGenerateRequest,
    EmailGenerateResponse,
    EmailMessageRead,
    EmailPreviewRequest,
    EmailPreviewResponse,
    EmailTemplateRead,
)
from app.services.email_generation.generator import (
    approve_email_message,
    generate_email_message,
    render_email_for_lead,
)
from app.services.email_generation.templates import list_templates

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/templates", response_model=list[EmailTemplateRead])
def get_email_templates(
    _ctx: WorkspaceContext = Depends(get_current_workspace),
) -> list[EmailTemplateRead]:
    return [
        EmailTemplateRead(id=template.id, name=template.name, subject=template.subject)
        for template in list_templates()
    ]


@router.post("/preview", response_model=EmailPreviewResponse)
def preview_email(
    payload: EmailPreviewRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailPreviewResponse:
    try:
        rendered = render_email_for_lead(
            db,
            payload.lead_id,
            ctx.workspace_id,
            sender_fallback_name=current_user.name,
            template_id=payload.template_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return EmailPreviewResponse(
        lead_id=payload.lead_id,
        template_id=rendered.template_id,
        recipient_email=rendered.recipient_email,
        subject=rendered.subject,
        body=rendered.body,
        variables=rendered.variables,
        has_opt_out_line=rendered.has_opt_out_line,
        compliance_errors=rendered.compliance_errors,
        can_send=not rendered.compliance_errors and rendered.has_opt_out_line,
    )


@router.post("/generate", response_model=EmailGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_email(
    payload: EmailGenerateRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailGenerateResponse:
    try:
        message = generate_email_message(
            db,
            payload.lead_id,
            ctx.workspace_id,
            sender_fallback_name=current_user.name,
            template_id=payload.template_id,
            campaign_id=payload.campaign_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return EmailGenerateResponse(
        message=EmailMessageRead.model_validate(message),
        compliance_errors=[],
    )


@router.post("/approve", response_model=EmailApproveResponse)
def approve_email(
    payload: EmailApproveRequest,
    ctx: WorkspaceContext = Depends(get_verified_workspace),
    db: Session = Depends(get_db),
) -> EmailApproveResponse:
    message = approve_email_message(
        db,
        payload.email_message_id,
        ctx.workspace_id,
        actor_id=ctx.user_id,
    )
    return EmailApproveResponse(message=EmailMessageRead.model_validate(message))
