from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace, get_verified_workspace
from app.core.database import get_db
from app.core.rate_limit import enforce
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
    EmailRegenerateRequest,
    EmailTemplateRead,
)
from app.services.email_generation.generator import (
    approve_email_message,
    generate_email_message,
    regenerate_email_message,
    render_email_for_lead,
)
from app.services.email_generation.templates import list_templates

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/templates", response_model=list[EmailTemplateRead])
def get_email_templates(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[EmailTemplateRead]:
    return [
        EmailTemplateRead(
            id=template.id,
            name=template.name,
            subject=template.subject,
            description=template.description,
            is_system=template.is_system,
        )
        for template in list_templates(db, ctx.workspace_id)
    ]


def _limit_ai(ctx: WorkspaceContext, mode: str) -> None:
    if mode == "ai":
        enforce("30/minute", "ai-draft", str(ctx.workspace_id))


@router.post("/preview", response_model=EmailPreviewResponse)
def preview_email(
    payload: EmailPreviewRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailPreviewResponse:
    _limit_ai(ctx, payload.mode)
    try:
        rendered = render_email_for_lead(
            db,
            payload.lead_id,
            ctx.workspace_id,
            sender_fallback_name=current_user.name,
            template_id=payload.template_id,
            mode=payload.mode,
            instructions=payload.instructions,
            user_id=current_user.id,
        )
        db.commit()  # keep the LLM usage record for previews
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
        generation_mode=rendered.generation_mode,
        llm_model=rendered.llm_model,
        generation_note=rendered.generation_note,
    )


@router.post("/generate", response_model=EmailGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_email(
    payload: EmailGenerateRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailGenerateResponse:
    _limit_ai(ctx, payload.mode)
    try:
        message = generate_email_message(
            db,
            payload.lead_id,
            ctx.workspace_id,
            sender_fallback_name=current_user.name,
            template_id=payload.template_id,
            campaign_id=payload.campaign_id,
            mode=payload.mode,
            instructions=payload.instructions,
            user_id=current_user.id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return EmailGenerateResponse(
        message=EmailMessageRead.model_validate(message),
        compliance_errors=[],
    )


@router.post("/{message_id}/regenerate", response_model=EmailMessageRead)
def regenerate_email(
    message_id: int,
    payload: EmailRegenerateRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailMessageRead:
    _limit_ai(ctx, payload.mode)
    try:
        message = regenerate_email_message(
            db,
            message_id,
            ctx.workspace_id,
            sender_fallback_name=current_user.name,
            mode=payload.mode,
            template_id=payload.template_id,
            instructions=payload.instructions,
            actor_id=current_user.id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EmailMessageRead.model_validate(message)


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
