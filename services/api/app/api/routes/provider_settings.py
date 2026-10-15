from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, get_verified_admin, require_admin
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.schemas.provider_settings import (
    ProviderCredentialListResponse,
    ProviderCredentialRead,
    ProviderCredentialUpsertRequest,
    ProviderTestResponse,
)
from app.services.provider_credentials.service import (
    activate_credential,
    configure_warmup,
    delete_credential,
    get_credential,
    list_credentials,
    record_test_result,
    upsert_credential,
    webhook_urls,
)
from app.services.provider_credentials.testing import test_provider_credential

router = APIRouter(prefix="/provider-settings", tags=["provider-settings"])


def _read(credential) -> ProviderCredentialRead:
    data = ProviderCredentialRead.model_validate(credential)
    data.webhook_urls = webhook_urls(credential)
    return data


class WarmupRequest(BaseModel):
    enabled: bool
    start_volume: int = Field(default=10, ge=1, le=1000)
    daily_increment: int = Field(default=5, ge=0, le=1000)
    maximum: int | None = Field(default=None, ge=1, le=100_000)


@router.get("", response_model=ProviderCredentialListResponse)
def get_provider_settings(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ProviderCredentialListResponse:
    items = list_credentials(db, ctx.workspace_id)
    return ProviderCredentialListResponse(
        items=[_read(item) for item in items],
    )


@router.post("", response_model=ProviderCredentialRead, status_code=status.HTTP_200_OK)
def upsert_provider_settings(
    payload: ProviderCredentialUpsertRequest,
    ctx: WorkspaceContext = Depends(get_verified_admin),
    db: Session = Depends(get_db),
) -> ProviderCredentialRead:
    try:
        credential = upsert_credential(
            db,
            ctx.workspace_id,
            ctx.user_id,
            payload.provider_type,
            payload.provider_name,
            payload.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _read(credential)


@router.patch("/{credential_id}/activate", response_model=ProviderCredentialRead)
def activate_provider_settings(
    credential_id: int,
    ctx: WorkspaceContext = Depends(get_verified_admin),
    db: Session = Depends(get_db),
) -> ProviderCredentialRead:
    try:
        credential = activate_credential(db, ctx.workspace_id, ctx.user_id, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _read(credential)


@router.post("/{credential_id}/test", response_model=ProviderTestResponse)
def test_provider_settings(
    credential_id: int,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProviderTestResponse:
    credential = get_credential(db, ctx.workspace_id, credential_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    success, message, tested_at = test_provider_credential(credential)
    record_test_result(db, credential, success=success, message=message, actor_id=ctx.user_id)
    return ProviderTestResponse(success=success, message=message, tested_at=tested_at)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_settings(
    credential_id: int,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_credential(db, ctx.workspace_id, ctx.user_id, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{credential_id}/warmup", response_model=ProviderCredentialRead)
def update_warmup(
    credential_id: int,
    payload: WarmupRequest,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProviderCredentialRead:
    credential = configure_warmup(
        db,
        ctx.workspace_id,
        ctx.user_id,
        credential_id,
        enabled=payload.enabled,
        start_volume=payload.start_volume,
        daily_increment=payload.daily_increment,
        maximum=payload.maximum,
    )
    return _read(credential)
