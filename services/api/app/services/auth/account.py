"""Self-serve account deletion."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.tenancy import system_session
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.services.auth.tokens import revoke_all_for_user


def deletion_blockers(db: Session, user: User) -> list[str]:
    """Workspaces that would be left without an owner if this user left."""
    blockers = []
    for membership in db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)):
        if membership.role != WorkspaceRole.OWNER:
            continue
        others = db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == membership.workspace_id,
                WorkspaceMember.user_id != user.id,
            )
        )
        other_owners = db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == membership.workspace_id,
                WorkspaceMember.user_id != user.id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        )
        if others and not other_owners:
            workspace = db.get(Workspace, membership.workspace_id)
            blockers.append(workspace.name if workspace else str(membership.workspace_id))
    return blockers


def delete_account(db: Session, user: User) -> None:
    """Delete the user, their memberships, and any workspace where they were the only member.

    Workspaces shared with others must have another owner first.
    """
    blockers = deletion_blockers(db, user)
    if blockers:
        raise ValidationFailedError(
            "You're the only owner of "
            + ", ".join(blockers)
            + ". Make another member an owner, or remove the other members, then try again.",
        )
    with system_session(db):
        for membership in list(
            db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
        ):
            others = db.scalar(
                select(func.count(WorkspaceMember.id)).where(
                    WorkspaceMember.workspace_id == membership.workspace_id,
                    WorkspaceMember.user_id != user.id,
                )
            )
            workspace = db.get(Workspace, membership.workspace_id)
            if not others and workspace is not None:
                db.delete(workspace)  # everything in it is removed with it (ON DELETE CASCADE)
            else:
                db.delete(membership)
        revoke_all_for_user(db, user.id)
        db.add(
            AuditLog(
                actor_id=None,
                action="account_deleted",
                entity_type="user",
                entity_id=user.id,
                metadata_={"email_domain": user.email.rsplit("@", 1)[-1]},
            )
        )
        db.delete(user)
        db.commit()
