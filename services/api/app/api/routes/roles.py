"""Permissions, custom roles (Enterprise) and the audit log."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.api.paging import PageParams, page_params
from app.core.database import get_db
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import DESCRIPTIONS, ROLE_PERMISSIONS, Permission, validate_permissions
from app.core.tenancy import WorkspaceContext
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workspace import CustomRole, WorkspaceMember
from app.services.billing.plans import features_for, require_feature
from app.services.common.csv_safety import safe_cell
from app.services.workspaces.service import audit

router = APIRouter(tags=["roles"])


class MyPermissions(BaseModel):
    role: str
    custom_role: str | None
    permissions: list[str]


class PermissionInfo(BaseModel):
    key: str
    description: str


class RoleRead(BaseModel):
    id: int | None
    name: str
    description: str | None
    permissions: list[str]
    built_in: bool
    member_count: int = 0


class RoleWrite(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = None


class AuditEntry(BaseModel):
    id: int
    created_at: datetime
    actor_id: int | None
    actor_name: str | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: int | None
    metadata: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    skip: int
    limit: int
    retention_days: int


@router.get("/workspaces/current/permissions", response_model=MyPermissions)
def my_permissions(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> MyPermissions:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ctx.workspace_id, WorkspaceMember.user_id == ctx.user_id
        )
    )
    return MyPermissions(
        role=str(ctx.role),
        custom_role=member.custom_role.name if member and member.custom_role else None,
        permissions=sorted(ctx.permissions),
    )


@router.get("/roles/permissions", response_model=list[PermissionInfo])
def list_permissions(
    _ctx: WorkspaceContext = Depends(get_current_workspace),
) -> list[PermissionInfo]:
    return [PermissionInfo(key=p.value, description=DESCRIPTIONS[p]) for p in Permission]


@router.get("/roles", response_model=list[RoleRead])
def list_roles(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> list[RoleRead]:
    counts = dict(
        db.execute(
            select(WorkspaceMember.custom_role_id, func.count(WorkspaceMember.id))
            .where(WorkspaceMember.workspace_id == ctx.workspace_id)
            .group_by(WorkspaceMember.custom_role_id)
        ).all()
    )
    built_in = [
        RoleRead(
            id=None, name=name.title(), description=None, permissions=sorted(perms), built_in=True
        )
        for name, perms in ROLE_PERMISSIONS.items()
    ]
    custom = db.scalars(
        select(CustomRole)
        .where(CustomRole.workspace_id == ctx.workspace_id)
        .order_by(CustomRole.name)
    ).all()
    return built_in + [
        RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(role.permissions or []),
            built_in=False,
            member_count=counts.get(role.id, 0),
        )
        for role in custom
    ]


def _grantable(ctx: WorkspaceContext, permissions: list[str]) -> list[str]:
    """Nobody can hand out a permission they don't hold themselves."""
    values = validate_permissions(permissions)
    missing = sorted(set(values) - ctx.permissions)
    if missing:
        raise PermissionDeniedError(
            f"You can't grant permissions you don't have: {', '.join(missing)}"
        )
    return values


def _get_role(db: Session, ctx: WorkspaceContext, role_id: int) -> CustomRole:
    role = db.scalar(
        select(CustomRole).where(
            CustomRole.id == role_id, CustomRole.workspace_id == ctx.workspace_id
        )
    )
    if role is None:
        raise NotFoundError("Role not found")
    return role


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
) -> RoleRead:
    require_feature(ctx.workspace, "custom_roles", "Custom roles")
    name = (payload.name or "").strip()
    if not name:
        raise ConflictError("Give the role a name")
    if db.scalar(
        select(CustomRole.id).where(
            CustomRole.workspace_id == ctx.workspace_id, CustomRole.name == name
        )
    ):
        raise ConflictError("A role with that name already exists")
    role = CustomRole(
        workspace_id=ctx.workspace_id,
        name=name,
        description=payload.description,
        permissions=_grantable(ctx, payload.permissions or []),
    )
    db.add(role)
    db.flush()
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "role.created",
        "workspace_role",
        role.id,
        {"permissions": role.permissions},
    )
    db.commit()
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        built_in=False,
    )


@router.patch("/roles/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    payload: RoleWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
) -> RoleRead:
    require_feature(ctx.workspace, "custom_roles", "Custom roles")
    role = _get_role(db, ctx, role_id)
    if payload.name and payload.name.strip() != role.name:
        name = payload.name.strip()
        if db.scalar(
            select(CustomRole.id).where(
                CustomRole.workspace_id == ctx.workspace_id, CustomRole.name == name
            )
        ):
            raise ConflictError("A role with that name already exists")
        role.name = name
    if payload.description is not None:
        role.description = payload.description
    if payload.permissions is not None:
        role.permissions = _grantable(ctx, payload.permissions)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "role.updated",
        "workspace_role",
        role.id,
        {"permissions": role.permissions},
    )
    db.commit()
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=sorted(role.permissions),
        built_in=False,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
) -> None:
    """Delete a custom role. Members who had it go back to the built-in member role."""
    role = _get_role(db, ctx, role_id)
    db.delete(role)
    audit(db, ctx.workspace_id, ctx.user_id, "role.deleted", "workspace_role", role_id)
    db.commit()


# --- audit log ---------------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _audit_query(
    ctx: WorkspaceContext,
    *,
    actor_id: int | None,
    action: str | None,
    entity_type: str | None,
    since: datetime | None,
    until: datetime | None,
) -> tuple[Any, int]:
    retention = features_for(ctx.workspace).audit_log_retention_days
    floor = datetime.now(UTC) - timedelta(days=retention)
    since, until = _aware(since), _aware(until)
    query = (
        select(AuditLog, User.name, User.email)
        .join(User, User.id == AuditLog.actor_id, isouter=True)
        .where(
            AuditLog.workspace_id == ctx.workspace_id,
            AuditLog.created_at >= max(floor, since or floor),
        )
    )
    if until:
        query = query.where(AuditLog.created_at <= until)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"{action.strip()}%"))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    return query, retention


def _entry(row: Any) -> AuditEntry:
    log, name, email = row
    return AuditEntry(
        id=log.id,
        created_at=log.created_at,
        actor_id=log.actor_id,
        actor_name=name,
        actor_email=email,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        metadata=log.metadata_,
    )


@router.get("/audit-logs", response_model=AuditPage)
def list_audit_logs(
    actor_id: int | None = None,
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    since: datetime | None = None,
    until: datetime | None = None,
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> AuditPage:
    query, retention = _audit_query(
        ctx, actor_id=actor_id, action=action, entity_type=entity_type, since=since, until=until
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(page.skip)
        .limit(page.limit)
    ).all()
    return AuditPage(
        items=[_entry(r) for r in rows],
        total=total,
        skip=page.skip,
        limit=page.limit,
        retention_days=retention,
    )


@router.get("/audit-logs/export")
def export_audit_logs(
    actor_id: int | None = None,
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    since: datetime | None = None,
    until: datetime | None = None,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> StreamingResponse:
    query, _ = _audit_query(
        ctx, actor_id=actor_id, action=action, entity_type=entity_type, since=since, until=until
    )
    rows = db.execute(query.order_by(AuditLog.created_at.desc()).limit(50_000)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["time", "actor", "action", "entity_type", "entity_id", "details"])
    for row in rows:
        entry = _entry(row)
        writer.writerow(
            [
                entry.created_at.isoformat(),
                safe_cell(entry.actor_email or "system"),
                safe_cell(entry.action),
                safe_cell(entry.entity_type),
                entry.entity_id or "",
                safe_cell(str(entry.metadata or "")),
            ]
        )
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )


@router.get("/workspaces/current/flags", response_model=dict[str, bool])
def workspace_flags(ctx: WorkspaceContext = Depends(get_current_workspace)) -> dict[str, bool]:
    """Which optional features are on for this workspace (server defaults plus admin overrides)."""
    from app.core.flags import FLAGS, feature_enabled

    return {name: feature_enabled(name, ctx.workspace) for name in FLAGS}
