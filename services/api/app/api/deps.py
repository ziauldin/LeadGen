from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.request_context import user_id_var
from app.core.security import read_access_token
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    claims = read_access_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("Invalid or expired token")
    user_id, token_version = claims

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise _unauthorized("Invalid or expired token")

    request.state.user_id = user.id
    user_id_var.set(user.id)
    return user


def require_verified_user(current_user: User = Depends(get_current_user)) -> User:
    """Gate actions that send email or invite people behind a confirmed email address."""
    if settings.require_email_verification and current_user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm your email address before doing this.",
        )
    return current_user


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
