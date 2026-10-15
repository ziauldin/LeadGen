"""Workspaces, memberships, invitations and workspace settings."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workspace import (
    ROLE_RANK,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceSettings,
)
from app.services.auth.tokens import hash_token

INVITATION_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "workspace")[:60]


def _unique_slug(db: Session, name: str) -> str:
    base = _slugify(name)
    slug = base
    while db.scalar(select(Workspace.id).where(Workspace.slug == slug)) is not None:
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


def audit(
    db: Session,
    workspace_id: int | None,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        ),
    )


def create_workspace(
    db: Session,
    owner: User,
    name: str,
    *,
    timezone: str = "UTC",
) -> Workspace:
    workspace = Workspace(
        name=name.strip()[:255] or "Workspace",
        slug=_unique_slug(db, name),
        timezone=timezone,
        created_by=owner.id,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.OWNER))
    db.add(WorkspaceSettings(workspace_id=workspace.id, sender_name=owner.name))
    owner.last_workspace_id = workspace.id
    audit(db, workspace.id, owner.id, "workspace_created", "workspace", workspace.id)
    db.flush()

    from app.services.provider_credentials.service import ensure_default_mock_credentials

    ensure_default_mock_credentials(db, workspace.id, owner.id)
    return workspace


def create_personal_workspace(db: Session, user: User) -> Workspace:
    first = user.name.split()[0] if user.name.strip() else "My"
    workspace = create_workspace(db, user, f"{first}'s workspace")
    db.commit()
    return workspace


def get_membership(db: Session, workspace_id: int, user_id: int) -> WorkspaceMember | None:
    return db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        ),
    )


def resolve_membership(
    db: Session,
    user: User,
    requested_workspace_id: int | None,
) -> WorkspaceMember:
    """Pick the workspace for this request: explicit header, last used, else the first one."""
    candidates = [requested_workspace_id] if requested_workspace_id else [user.last_workspace_id]
    for workspace_id in candidates:
        if workspace_id is None:
            continue
        membership = get_membership(db, workspace_id, user.id)
        if membership is not None and membership.workspace.deleted_at is None:
            return membership
        if requested_workspace_id:
            # Never reveal whether a workspace exists to non-members.
            raise NotFoundError("Workspace not found")

    membership = db.scalar(
        select(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id, Workspace.deleted_at.is_(None))
        .order_by(WorkspaceMember.id),
    )
    if membership is None:
        # Users created before workspaces existed (or whose last workspace was deleted).
        create_personal_workspace(db, user)
        membership = get_membership(db, user.last_workspace_id or 0, user.id)
        assert membership is not None  # noqa: S101 - just created
    return membership


def list_user_workspaces(db: Session, user_id: int) -> list[tuple[Workspace, str]]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id, Workspace.deleted_at.is_(None))
        .order_by(Workspace.created_at),
    ).all()
    return [(workspace, role) for workspace, role in rows]


def switch_workspace(db: Session, user: User, workspace_id: int) -> Workspace:
    membership = get_membership(db, workspace_id, user.id)
    if membership is None:
        raise NotFoundError("Workspace not found")
    user.last_workspace_id = workspace_id
    db.commit()
    return membership.workspace


def get_or_create_settings(db: Session, workspace_id: int) -> WorkspaceSettings:
    settings = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id),
    )
    if settings is None:
        settings = WorkspaceSettings(workspace_id=workspace_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


# --- Members ---------------------------------------------------------------------------------


def list_members(db: Session, workspace_id: int) -> list[WorkspaceMember]:
    return list(
        db.scalars(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.id),
        ).all(),
    )


def _owner_count(db: Session, workspace_id: int) -> int:
    return (
        db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            ),
        )
        or 0
    )


def change_member_role(
    db: Session,
    *,
    workspace_id: int,
    actor: WorkspaceMember,
    user_id: int,
    role: WorkspaceRole,
) -> WorkspaceMember:
    member = get_membership(db, workspace_id, user_id)
    if member is None:
        raise NotFoundError("Member not found")
    actor_rank = ROLE_RANK[WorkspaceRole(actor.role)]
    if role == WorkspaceRole.OWNER or member.role == WorkspaceRole.OWNER:
        if actor.role != WorkspaceRole.OWNER:
            raise PermissionDeniedError("Only an owner can grant or remove the owner role")
    elif ROLE_RANK[role] > actor_rank:
        raise PermissionDeniedError("You cannot grant a role higher than your own")
    if (
        member.role == WorkspaceRole.OWNER
        and role != WorkspaceRole.OWNER
        and _owner_count(db, workspace_id) <= 1
    ):
        raise ValidationFailedError("A workspace must keep at least one owner")
    old_role = member.role
    member.role = role
    audit(
        db,
        workspace_id,
        actor.user_id,
        "member_role_changed",
        "user",
        user_id,
        {"from": old_role, "to": role.value},
    )
    db.commit()
    return member


def remove_member(db: Session, *, workspace_id: int, actor: WorkspaceMember, user_id: int) -> None:
    member = get_membership(db, workspace_id, user_id)
    if member is None:
        raise NotFoundError("Member not found")
    leaving_self = user_id == actor.user_id
    if (
        not leaving_self
        and ROLE_RANK[WorkspaceRole(member.role)] >= ROLE_RANK[WorkspaceRole(actor.role)]
        and actor.role != WorkspaceRole.OWNER
    ):
        raise PermissionDeniedError("You cannot remove a member with an equal or higher role")
    if member.role == WorkspaceRole.OWNER and _owner_count(db, workspace_id) <= 1:
        raise ValidationFailedError("A workspace must keep at least one owner")
    db.delete(member)
    user = db.get(User, user_id)
    if user is not None and user.last_workspace_id == workspace_id:
        user.last_workspace_id = None
    audit(db, workspace_id, actor.user_id, "member_removed", "user", user_id)
    db.commit()


# --- Invitations -----------------------------------------------------------------------------


def create_invitation(
    db: Session,
    *,
    workspace: Workspace,
    inviter: User,
    inviter_role: WorkspaceRole,
    email: str,
    role: WorkspaceRole,
) -> tuple[WorkspaceInvitation, str]:
    normalized = email.strip().lower()
    if role == WorkspaceRole.OWNER:
        raise ValidationFailedError("Invite as admin or member, then transfer ownership")
    if ROLE_RANK[role] > ROLE_RANK[inviter_role]:
        raise PermissionDeniedError("You cannot invite someone with a higher role than yours")
    existing_user = db.scalar(select(User).where(User.email == normalized))
    if existing_user and get_membership(db, workspace.id, existing_user.id):
        raise ConflictError("That person is already a member of this workspace")

    pending = db.scalars(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace.id,
            WorkspaceInvitation.email == normalized,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.revoked_at.is_(None),
        ),
    ).all()
    for invitation in pending:
        invitation.revoked_at = _now()

    raw = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        workspace_id=workspace.id,
        email=normalized,
        role=role,
        token_hash=hash_token(raw),
        invited_by=inviter.id,
        expires_at=_now() + INVITATION_TTL,
    )
    db.add(invitation)
    db.flush()
    audit(
        db,
        workspace.id,
        inviter.id,
        "invitation_created",
        "workspace_invitation",
        invitation.id,
        {"email": normalized, "role": role.value},
    )
    db.commit()
    db.refresh(invitation)
    return invitation, raw


def list_invitations(db: Session, workspace_id: int) -> list[WorkspaceInvitation]:
    return list(
        db.scalars(
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.accepted_at.is_(None),
                WorkspaceInvitation.revoked_at.is_(None),
            )
            .order_by(WorkspaceInvitation.created_at.desc()),
        ).all(),
    )


def revoke_invitation(db: Session, workspace_id: int, invitation_id: int, actor_id: int) -> None:
    invitation = db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
        ),
    )
    if invitation is None or invitation.accepted_at is not None:
        raise NotFoundError("Invitation not found")
    invitation.revoked_at = _now()
    audit(db, workspace_id, actor_id, "invitation_revoked", "workspace_invitation", invitation_id)
    db.commit()


def find_invitation(db: Session, raw_token: str) -> WorkspaceInvitation:
    invitation = db.scalar(
        select(WorkspaceInvitation).where(WorkspaceInvitation.token_hash == hash_token(raw_token)),
    )
    if (
        invitation is None
        or invitation.revoked_at is not None
        or invitation.accepted_at is not None
        or _aware(invitation.expires_at) <= _now()
    ):
        raise NotFoundError("This invitation is invalid or has expired")
    return invitation


def accept_invitation(db: Session, raw_token: str, user: User) -> Workspace:
    invitation = find_invitation(db, raw_token)
    if invitation.email != user.email:
        raise PermissionDeniedError(
            "This invitation was sent to a different email address. "
            "Sign in with that address to accept it.",
        )
    if get_membership(db, invitation.workspace_id, user.id) is None:
        db.add(
            WorkspaceMember(
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                role=invitation.role,
            ),
        )
    invitation.accepted_at = _now()
    user.last_workspace_id = invitation.workspace_id
    if user.email_verified_at is None:
        # Opening the emailed link proves ownership of the address.
        user.email_verified_at = _now()
    audit(
        db,
        invitation.workspace_id,
        user.id,
        "invitation_accepted",
        "workspace_invitation",
        invitation.id,
    )
    db.commit()
    return invitation.workspace
