from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.suppression import Suppression
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate
from app.schemas.suppression import SuppressionCreate, SuppressionListResponse, SuppressionRead

router = APIRouter(prefix="/settings", tags=["settings"])
suppressions_router = APIRouter(prefix="/suppressions", tags=["suppressions"])


def _get_or_create_settings(db: Session, user: User) -> UserSettings:
    settings = db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_model=UserSettingsRead)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    return _get_or_create_settings(db, current_user)


@router.patch("", response_model=UserSettingsRead)
def update_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    settings = _get_or_create_settings(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@suppressions_router.get("", response_model=SuppressionListResponse)
def list_suppressions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionListResponse:
    total = db.scalar(select(func.count(Suppression.id))) or 0
    items = db.scalars(
        select(Suppression).order_by(Suppression.created_at.desc()).offset(skip).limit(limit),
    ).all()
    return SuppressionListResponse(
        items=[SuppressionRead.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@suppressions_router.post("", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
def create_suppression(
    payload: SuppressionCreate,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Suppression:
    email = payload.email.lower().strip() if payload.email else None
    domain = payload.domain.lower().strip() if payload.domain else None

    existing_query = select(Suppression)
    if email:
        existing_query = existing_query.where(Suppression.email == email)
    elif domain:
        existing_query = existing_query.where(Suppression.domain == domain)

    existing = db.scalar(existing_query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suppression already exists",
        )

    suppression = Suppression(
        email=email,
        domain=domain,
        reason=payload.reason,
        source=payload.source or "manual",
    )
    db.add(suppression)
    db.commit()
    db.refresh(suppression)
    return suppression


@suppressions_router.delete("/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suppression(
    suppression_id: int,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    suppression = db.get(Suppression, suppression_id)
    if suppression is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression not found")
    db.delete(suppression)
    db.commit()
