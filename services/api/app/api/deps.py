from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_token_subject
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = get_token_subject(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_owned_niche(
    niche_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Niche:
    niche = db.scalar(
        select(Niche).where(Niche.id == niche_id, Niche.user_id == current_user.id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    return niche


def get_owned_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Lead:
    lead = db.scalar(
        select(Lead)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Lead.id == lead_id, Niche.user_id == current_user.id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
