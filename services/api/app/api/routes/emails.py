from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
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
    _current_user: User = Depends(get_current_user),
) -> list[EmailTemplateRead]:
    return [
        EmailTemplateRead(id=template.id, name=template.name, subject=template.subject)
        for template in list_templates()
    ]


@router.post("/preview", response_model=EmailPreviewResponse)
def preview_email(
    payload: EmailPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailPreviewResponse:
    try:
        rendered = render_email_for_lead(
            db,
            payload.lead_id,
            current_user.id,
            template_id=payload.template_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailGenerateResponse:
    try:
        message = generate_email_message(
            db,
            payload.lead_id,
            current_user.id,
            template_id=payload.template_id,
            campaign_id=payload.campaign_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return EmailGenerateResponse(
        message=EmailMessageRead.model_validate(message),
        compliance_errors=[],
    )


@router.post("/approve", response_model=EmailApproveResponse)
def approve_email(
    payload: EmailApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailApproveResponse:
    try:
        message = approve_email_message(db, payload.email_message_id, current_user.id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return EmailApproveResponse(message=EmailMessageRead.model_validate(message))
