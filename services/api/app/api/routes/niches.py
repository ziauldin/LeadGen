from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_niche
from app.core.database import get_db
from app.models.niche import Niche
from app.models.user import User
from app.schemas.niche import NicheCreate, NicheListResponse, NicheRead, NicheUpdate

router = APIRouter(prefix="/niches", tags=["niches"])


@router.get("", response_model=NicheListResponse)
def list_niches(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NicheListResponse:
    total = db.scalar(
        select(func.count(Niche.id)).where(Niche.user_id == current_user.id),
    ) or 0
    niches = db.scalars(
        select(Niche)
        .where(Niche.user_id == current_user.id)
        .order_by(Niche.created_at.desc())
        .offset(skip)
        .limit(limit),
    ).all()
    return NicheListResponse(
        items=[NicheRead.model_validate(niche) for niche in niches],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=NicheRead, status_code=status.HTTP_201_CREATED)
def create_niche(
    payload: NicheCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Niche:
    niche = Niche(user_id=current_user.id, **payload.model_dump())
    db.add(niche)
    db.commit()
    db.refresh(niche)
    return niche


@router.get("/{niche_id}", response_model=NicheRead)
def get_niche(niche: Niche = Depends(get_owned_niche)) -> Niche:
    return niche


@router.patch("/{niche_id}", response_model=NicheRead)
def update_niche(
    payload: NicheUpdate,
    niche: Niche = Depends(get_owned_niche),
    db: Session = Depends(get_db),
) -> Niche:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(niche, field, value)
    db.commit()
    db.refresh(niche)
    return niche


@router.delete("/{niche_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_niche(
    niche: Niche = Depends(get_owned_niche),
    db: Session = Depends(get_db),
) -> None:
    db.delete(niche)
    db.commit()
