from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_current_workspace,
    get_verified_admin,
    require_admin,
    require_verified_user,
)
from app.core.database import get_db
from app.core.rate_limit import enforce
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign
from app.models.enums import ProviderName, ProviderType
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceRole
from app.schemas.auth import MessageResponse
from app.schemas.workspace import (
    InvitationCreate,
    InvitationPreview,
    InvitationRead,
    MemberRead,
    MemberUpdate,
    OnboardingStatus,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithRole,
)
from app.services.platform_email.dispatch import send_platform_email
from app.services.platform_email.templates import invitation_email
from app.services.workspaces import service as workspaces

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
invitations_router = APIRouter(prefix="/invitations", tags=["workspaces"])


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceListResponse:
    rows = workspaces.list_user_workspaces(db, current_user.id)
    return WorkspaceListResponse(
        items=[
            WorkspaceWithRole(
                **WorkspaceRead.model_validate(ws).model_dump(),
                role=WorkspaceRole(role),
            )
            for ws, role in rows
        ],
        current_workspace_id=current_user.last_workspace_id,
    )


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> Workspace:
    enforce("10/day", "create-workspace", str(current_user.id))
    workspace = workspaces.create_workspace(
        db,
        current_user,
        payload.name,
        timezone=payload.timezone,
    )
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/current", response_model=WorkspaceWithRole)
def get_current(ctx: WorkspaceContext = Depends(get_current_workspace)) -> WorkspaceWithRole:
    return WorkspaceWithRole(
        **WorkspaceRead.model_validate(ctx.workspace).model_dump(),
        role=ctx.role,
    )


@router.patch("/current", response_model=WorkspaceRead)
def update_current(
    payload: WorkspaceUpdate,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = db.get(Workspace, ctx.workspace_id)
    assert workspace is not None  # noqa: S101 - resolved by the dependency
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    workspaces.audit(
        db, ctx.workspace_id, ctx.user_id, "workspace_updated", "workspace", workspace.id
    )
    db.commit()
    db.refresh(workspace)
    return workspace


@router.post("/{workspace_id}/switch", response_model=WorkspaceRead)
def switch(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    return workspaces.switch_workspace(db, current_user, workspace_id)


@router.get("/current/members", response_model=list[MemberRead])
def list_members(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[MemberRead]:
    return [
        MemberRead(
            user_id=member.user_id,
            name=member.user.name,
            email=member.user.email,
            role=WorkspaceRole(member.role),
            joined_at=member.created_at,
        )
        for member in workspaces.list_members(db, ctx.workspace_id)
    ]


@router.patch("/current/members/{user_id}", response_model=MemberRead)
def update_member(
    user_id: int,
    payload: MemberUpdate,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MemberRead:
    actor = workspaces.get_membership(db, ctx.workspace_id, ctx.user_id)
    assert actor is not None  # noqa: S101 - resolved by the dependency
    member = workspaces.change_member_role(
        db,
        workspace_id=ctx.workspace_id,
        actor=actor,
        user_id=user_id,
        role=payload.role,
    )
    return MemberRead(
        user_id=member.user_id,
        name=member.user.name,
        email=member.user.email,
        role=WorkspaceRole(member.role),
        joined_at=member.created_at,
    )


@router.delete("/current/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    actor = workspaces.get_membership(db, ctx.workspace_id, ctx.user_id)
    assert actor is not None  # noqa: S101 - resolved by the dependency
    if user_id != ctx.user_id and not ctx.has_role(WorkspaceRole.ADMIN):
        from app.core.errors import PermissionDeniedError

        raise PermissionDeniedError("Only admins can remove other members")
    workspaces.remove_member(db, workspace_id=ctx.workspace_id, actor=actor, user_id=user_id)


@router.get("/current/invitations", response_model=list[InvitationRead])
def list_invitations(
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    return workspaces.list_invitations(db, ctx.workspace_id)


@router.post(
    "/current/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: InvitationCreate,
    ctx: WorkspaceContext = Depends(get_verified_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce("30/day", "invitations", str(ctx.workspace_id))
    from app.services.billing.usage import check_seat_available

    check_seat_available(db, ctx.workspace)
    invitation, raw = workspaces.create_invitation(
        db,
        workspace=ctx.workspace,
        inviter=current_user,
        inviter_role=ctx.role,
        email=str(payload.email),
        role=payload.role,
    )
    send_platform_email(
        invitation_email(invitation.email, current_user.name, ctx.workspace.name, raw),
    )
    return invitation


@router.delete("/current/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: int,
    ctx: WorkspaceContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    workspaces.revoke_invitation(db, ctx.workspace_id, invitation_id, ctx.user_id)


@router.get("/current/onboarding", response_model=OnboardingStatus)
def onboarding(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatus:
    ws = ctx.workspace_id
    settings_row = workspaces.get_or_create_settings(db, ws)
    sending = db.scalar(
        select(ProviderCredential.id).where(
            ProviderCredential.workspace_id == ws,
            ProviderCredential.provider_type == ProviderType.EMAIL,
            ProviderCredential.is_active.is_(True),
            ProviderCredential.provider_name != ProviderName.MOCK,
        ),
    )
    steps = {
        "email_verified": current_user.email_verified_at is not None,
        "sender_profile": bool(settings_row.sender_name and settings_row.business_address),
        "sending_provider": sending is not None,
        "niche_created": db.scalar(select(Niche.id).where(Niche.workspace_id == ws).limit(1))
        is not None,
        "leads_added": db.scalar(select(Lead.id).where(Lead.workspace_id == ws).limit(1))
        is not None,
        "campaign_created": db.scalar(
            select(Campaign.id).where(Campaign.workspace_id == ws).limit(1),
        )
        is not None,
    }
    return OnboardingStatus(**steps, completed=all(steps.values()))


@invitations_router.get("/{token}", response_model=InvitationPreview)
def preview_invitation(token: str, db: Session = Depends(get_db)) -> InvitationPreview:
    invitation = workspaces.find_invitation(db, token)
    return InvitationPreview(
        workspace_name=invitation.workspace.name,
        email=invitation.email,
        role=WorkspaceRole(invitation.role),
        expires_at=invitation.expires_at,
    )


@invitations_router.post("/{token}/accept", response_model=WorkspaceRead)
def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    return workspaces.accept_invitation(db, token, current_user)


@router.post("/current/leave", response_model=MessageResponse)
def leave_workspace(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> MessageResponse:
    actor = workspaces.get_membership(db, ctx.workspace_id, ctx.user_id)
    assert actor is not None  # noqa: S101 - resolved by the dependency
    workspaces.remove_member(db, workspace_id=ctx.workspace_id, actor=actor, user_id=ctx.user_id)
    return MessageResponse(message="You left the workspace")
