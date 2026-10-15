from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.rate_limit import enforce
from app.core.request_context import user_id_var, workspace_id_var
from app.core.security import read_access_token
from app.core.tenancy import WorkspaceContext, bind_session
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.services.workspaces.service import resolve_membership

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


def get_current_workspace(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_workspace_id: int | None = Header(default=None, alias="X-Workspace-Id"),
) -> WorkspaceContext:
    """Resolve and authorise the workspace for this request, and scope the DB session to it."""
    membership = resolve_membership(db, current_user, x_workspace_id)
    ctx = WorkspaceContext(
        workspace_id=membership.workspace_id,
        user_id=current_user.id,
        role=WorkspaceRole(membership.role),
        workspace=membership.workspace,
    )
    enforce(app_settings.rate_limit_default, "workspace", str(ctx.workspace_id))
    bind_session(db, ctx.workspace_id)
    request.state.workspace_id = ctx.workspace_id
    workspace_id_var.set(ctx.workspace_id)
    return ctx


def require_role(minimum: WorkspaceRole) -> Callable[..., WorkspaceContext]:
    def dependency(ctx: WorkspaceContext = Depends(get_current_workspace)) -> WorkspaceContext:
        if not ctx.has_role(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action needs the {minimum.value} role in this workspace.",
            )
        return ctx

    return dependency


require_admin = require_role(WorkspaceRole.ADMIN)
require_owner = require_role(WorkspaceRole.OWNER)


def require_verified_user(current_user: User = Depends(get_current_user)) -> User:
    """Gate actions that send email or invite people behind a confirmed email address."""
    if settings.require_email_verification and current_user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm your email address before doing this.",
        )
    return current_user


def get_verified_workspace(
    _user: User = Depends(require_verified_user),
    ctx: WorkspaceContext = Depends(get_current_workspace),
) -> WorkspaceContext:
    return ctx


def get_verified_admin(
    _user: User = Depends(require_verified_user),
    ctx: WorkspaceContext = Depends(require_admin),
) -> WorkspaceContext:
    return ctx


def get_owned_niche(
    niche_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Niche:
    niche = db.scalar(
        select(Niche).where(Niche.id == niche_id, Niche.workspace_id == ctx.workspace_id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    return niche


def get_owned_lead(
    lead_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Lead:
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == lead_id, Lead.workspace_id == ctx.workspace_id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
