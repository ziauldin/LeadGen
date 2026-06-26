from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.provider_settings import (
    ProviderCredentialListResponse,
    ProviderCredentialRead,
    ProviderCredentialUpsertRequest,
    ProviderTestResponse,
)
from app.services.provider_credentials.service import (
    activate_credential,
    delete_credential,
    list_credentials,
    record_test_result,
    upsert_credential,
)
from app.services.provider_credentials.testing import test_provider_credential

router = APIRouter(prefix="/provider-settings", tags=["provider-settings"])


@router.get("", response_model=ProviderCredentialListResponse)
def get_provider_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderCredentialListResponse:
    items = list_credentials(db, current_user.id)
    return ProviderCredentialListResponse(
        items=[ProviderCredentialRead.model_validate(item) for item in items],
    )


@router.post("", response_model=ProviderCredentialRead, status_code=status.HTTP_200_OK)
def upsert_provider_settings(
    payload: ProviderCredentialUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderCredentialRead:
    try:
        credential = upsert_credential(
            db,
            current_user,
            payload.provider_type,
            payload.provider_name,
            payload.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProviderCredentialRead.model_validate(credential)


@router.patch("/{credential_id}/activate", response_model=ProviderCredentialRead)
def activate_provider_settings(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderCredentialRead:
    try:
        credential = activate_credential(db, current_user, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProviderCredentialRead.model_validate(credential)


@router.post("/{credential_id}/test", response_model=ProviderTestResponse)
def test_provider_settings(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderTestResponse:
    from app.services.provider_credentials.service import get_credential

    credential = get_credential(db, current_user.id, credential_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    success, message, tested_at = test_provider_credential(credential)
    record_test_result(db, credential, success=success, message=message, actor_id=current_user.id)
    return ProviderTestResponse(success=success, message=message, tested_at=tested_at)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_settings(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_credential(db, current_user, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
