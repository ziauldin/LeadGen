"""Platform admin back office. Every route needs a superuser; every change is audited."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_superuser
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.flags import FLAGS, feature_enabled
from app.core.security import create_access_token
from app.core.tenancy import sync_rls
from app.models.audit_log import AuditLog
from app.models.suppression import Suppression
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.suppression import SuppressionRead
from app.services.admin.service import (
    abuse_queue,
    overview,
    system_health,
    validate_flags,
    validate_overrides,
    workspace_rows,
)
from app.services.billing.plans import METRIC_PERIOD, PLANS, features_for, limits_for
from app.services.billing.usage import current_usage
from app.services.workspaces.service import audit

router = APIRouter(prefix="/admin", tags=["admin"])


def admin_db(
    db: Session = Depends(get_db), admin: User = Depends(require_superuser)
) -> Iterator[Session]:
    """The request's session, unscoped: admins see every workspace."""
    db.info["tenant_bypass"] = True
    db.info.pop("workspace_id", None)
    sync_rls(db)
    yield db


class WorkspaceRow(BaseModel):
    id: int
    name: str
    plan: str
    owner_email: str | None
    members: int
    leads: int
    sent_30d: int
    bounce_rate_30d: float
    complaint_rate_30d: float
    sending_suspended_at: datetime | None
    sending_suspended_reason: str | None
    deleted_at: datetime | None
    created_at: datetime


class WorkspacePage(BaseModel):
    items: list[WorkspaceRow]
    total: int
    skip: int
    limit: int


class MemberRow(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    mfa_enabled: bool


class WorkspaceDetail(WorkspaceRow):
    plan_overrides: dict[str, Any] | None
    feature_flags: dict[str, bool] | None
    effective_flags: dict[str, bool]
    limits: dict[str, int]
    features: dict[str, bool | int]
    usage: dict[str, int]
    members_list: list[MemberRow]


class WorkspacePatch(BaseModel):
    plan: str | None = None
    plan_overrides: dict[str, Any] | None = None
    feature_flags: dict[str, bool | None] | None = None
    note: str | None = Field(default=None, max_length=500)


class SuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ImpersonateRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    user_id: int | None = None  # defaults to a workspace owner
    write: bool = False
    minutes: int = Field(default=30, ge=5, le=240)


class ImpersonationToken(BaseModel):
    access_token: str
    workspace_id: int
    workspace_name: str
    user_name: str
    user_email: str
    read_only: bool
    expires_at: datetime


class UserRow(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    is_superuser: bool
    mfa_enabled: bool
    email_verified_at: datetime | None
    created_at: datetime
    workspaces: int


class UserPage(BaseModel):
    items: list[UserRow]
    total: int


class GlobalSuppressionCreate(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=500)


class AdminAuditRow(BaseModel):
    id: int
    created_at: datetime
    workspace_id: int | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: int | None
    metadata: dict[str, Any] | None


def _workspace(db: Session, workspace_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace not found")
    return workspace


def _detail(db: Session, workspace: Workspace) -> WorkspaceDetail:
    row = workspace_rows(db, [workspace])[0]
    members = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace.id)
        .order_by(WorkspaceMember.id)
    ).all()
    return WorkspaceDetail(
        **row,
        plan_overrides=workspace.plan_overrides,
        feature_flags=workspace.feature_flags,
        effective_flags={name: feature_enabled(name, workspace) for name in FLAGS},
        limits=limits_for(workspace).as_dict(),
        features=features_for(workspace).as_dict(),
        usage={metric: current_usage(db, workspace.id, metric) for metric in METRIC_PERIOD},
        members_list=[
            MemberRow(
                user_id=u.id,
                name=u.name,
                email=u.email,
                role=str(m.role),
                mfa_enabled=u.mfa_enabled,
            )
            for m, u in members
        ],
    )


@router.get("/overview")
def get_overview(db: Session = Depends(admin_db)) -> dict[str, Any]:
    return overview(db)


@router.get("/health")
def get_health(db: Session = Depends(admin_db)) -> dict[str, Any]:
    return system_health(db)


@router.get("/abuse")
def get_abuse(db: Session = Depends(admin_db)) -> dict[str, Any]:
    return abuse_queue(db)


@router.get("/flags")
def list_flags() -> dict[str, Any]:
    return {
        "flags": [
            {"key": key, "description": text, "default": bool(getattr(settings, f"feature_{key}"))}
            for key, text in FLAGS.items()
        ],
        "plans": list(PLANS),
    }


# --- workspaces ----------------------------------------------------------------------------------


@router.get("/workspaces", response_model=WorkspacePage)
def list_workspaces(
    search: str | None = Query(default=None, max_length=255),
    plan: str | None = Query(default=None, max_length=30),
    suspended: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(admin_db),
) -> WorkspacePage:
    conditions: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        owner_match = (
            select(WorkspaceMember.workspace_id)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(User.email.ilike(pattern))
        )
        conditions.append(or_(Workspace.name.ilike(pattern), Workspace.id.in_(owner_match)))
    if plan:
        conditions.append(Workspace.plan == plan)
    if suspended is not None:
        conditions.append(
            Workspace.sending_suspended_at.is_not(None)
            if suspended
            else Workspace.sending_suspended_at.is_(None)
        )
    total = db.scalar(select(func.count(Workspace.id)).where(*conditions)) or 0
    workspaces = list(
        db.scalars(
            select(Workspace)
            .where(*conditions)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )
    return WorkspacePage(
        items=[WorkspaceRow(**r) for r in workspace_rows(db, workspaces)],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: int, db: Session = Depends(admin_db)) -> WorkspaceDetail:
    return _detail(db, _workspace(db, workspace_id))


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: int,
    payload: WorkspacePatch,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> WorkspaceDetail:
    workspace = _workspace(db, workspace_id)
    changes: dict[str, Any] = {}
    if payload.plan is not None:
        if payload.plan not in PLANS:
            raise ValidationFailedError(f"Unknown plan {payload.plan}")
        changes["plan"] = {"from": workspace.plan, "to": payload.plan}
        workspace.plan = payload.plan
    if payload.plan_overrides is not None:
        workspace.plan_overrides = validate_overrides(payload.plan_overrides) or None
        changes["plan_overrides"] = workspace.plan_overrides
    if payload.feature_flags is not None:
        merged = {**(workspace.feature_flags or {})}
        for key, value in payload.feature_flags.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        workspace.feature_flags = validate_flags(merged) or None
        changes["feature_flags"] = workspace.feature_flags
    audit(
        db,
        workspace.id,
        admin.id,
        "admin.workspace_updated",
        "workspace",
        workspace.id,
        {**changes, "note": payload.note},
    )
    db.commit()
    return _detail(db, workspace)


@router.post("/workspaces/{workspace_id}/suspend", response_model=WorkspaceDetail)
def suspend_workspace(
    workspace_id: int,
    payload: SuspendRequest,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> WorkspaceDetail:
    workspace = _workspace(db, workspace_id)
    workspace.sending_suspended_at = datetime.now(UTC)
    workspace.sending_suspended_reason = payload.reason
    audit(
        db,
        workspace.id,
        admin.id,
        "admin.sending_suspended",
        "workspace",
        workspace.id,
        {"reason": payload.reason},
    )
    db.commit()
    return _detail(db, workspace)


@router.post("/workspaces/{workspace_id}/unsuspend", response_model=WorkspaceDetail)
def unsuspend_workspace(
    workspace_id: int,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> WorkspaceDetail:
    workspace = _workspace(db, workspace_id)
    workspace.sending_suspended_at = None
    workspace.sending_suspended_reason = None
    audit(db, workspace.id, admin.id, "admin.sending_resumed", "workspace", workspace.id)
    db.commit()
    return _detail(db, workspace)


@router.post("/workspaces/{workspace_id}/impersonate", response_model=ImpersonationToken)
def impersonate(
    workspace_id: int,
    payload: ImpersonateRequest,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> ImpersonationToken:
    """A short-lived token to view the app as a member. Read-only unless ``write`` is set."""
    workspace = _workspace(db, workspace_id)
    minutes = min(payload.minutes, settings.impersonation_max_minutes)
    query = (
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace.id)
    )
    if payload.user_id is not None:
        query = query.where(User.id == payload.user_id)
    else:
        query = query.where(WorkspaceMember.role == WorkspaceRole.OWNER).order_by(
            WorkspaceMember.id
        )
    target = db.scalars(query).first()
    if target is None:
        raise NotFoundError("That person isn't a member of this workspace")
    if target.is_superuser or not target.is_active:
        raise ValidationFailedError("You can't impersonate this account")
    expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
    token = create_access_token(
        target.id,
        token_version=target.token_version,
        expires_delta=timedelta(minutes=minutes),
        extra_claims={"imp": admin.id, "ro": not payload.write, "wsp": workspace.id},
    )
    # Recorded in the customer's own audit log too.
    audit(
        db,
        workspace.id,
        admin.id,
        "admin.impersonation_started",
        "user",
        target.id,
        {
            "reason": payload.reason,
            "read_only": not payload.write,
            "minutes": minutes,
            "admin": admin.email,
        },
    )
    db.commit()
    return ImpersonationToken(
        access_token=token,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        user_name=target.name,
        user_email=target.email,
        read_only=not payload.write,
        expires_at=expires_at,
    )


# --- users ---------------------------------------------------------------------------------------


@router.get("/users", response_model=UserPage)
def list_users(
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(admin_db),
) -> UserPage:
    conditions: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    users = db.scalars(
        select(User).where(*conditions).order_by(User.created_at.desc()).offset(skip).limit(limit)
    ).all()
    counts = dict(
        db.execute(
            select(WorkspaceMember.user_id, func.count(WorkspaceMember.id))
            .where(WorkspaceMember.user_id.in_([u.id for u in users]))
            .group_by(WorkspaceMember.user_id)
        ).all()
    )
    return UserPage(
        items=[
            UserRow(
                id=u.id,
                name=u.name,
                email=u.email,
                is_active=u.is_active,
                is_superuser=u.is_superuser,
                mfa_enabled=u.mfa_enabled,
                email_verified_at=u.email_verified_at,
                created_at=u.created_at,
                workspaces=int(counts.get(u.id, 0)),
            )
            for u in users
        ],
        total=total,
    )


def _set_active(db: Session, admin: User, user_id: int, active: bool) -> dict[str, bool]:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id:
        raise ValidationFailedError("You can't disable your own account")
    user.is_active = active
    if not active:
        user.token_version += 1  # signs them out everywhere
    audit(
        db,
        None,
        admin.id,
        "admin.user_enabled" if active else "admin.user_disabled",
        "user",
        user.id,
        {"email": user.email},
    )
    db.commit()
    return {"is_active": active}


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: int, db: Session = Depends(admin_db), admin: User = Depends(require_superuser)
) -> dict[str, bool]:
    return _set_active(db, admin, user_id, False)


@router.post("/users/{user_id}/enable")
def enable_user(
    user_id: int, db: Session = Depends(admin_db), admin: User = Depends(require_superuser)
) -> dict[str, bool]:
    return _set_active(db, admin, user_id, True)


# --- platform-wide suppressions -------------------------------------------------------------------


@router.get("/suppressions", response_model=list[SuppressionRead])
def list_global_suppressions(
    search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(admin_db),
) -> Any:
    query = select(Suppression).where(Suppression.workspace_id.is_(None))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(Suppression.email.ilike(pattern), Suppression.domain.ilike(pattern))
        )
    return db.scalars(query.order_by(Suppression.created_at.desc()).limit(limit)).all()


@router.post("/suppressions", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
def create_global_suppression(
    payload: GlobalSuppressionCreate,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> Any:
    email = payload.email.strip().lower() if payload.email else None
    domain = None if email else (payload.domain or "").strip().lower().lstrip("@") or None
    if not email and not domain:
        raise ValidationFailedError("Enter an email address or a domain")
    suppression = Suppression(
        workspace_id=None,
        email=email,
        domain=domain,
        reason=payload.reason,
        source="platform",
        reason_code="manual",
    )
    db.add(suppression)
    db.flush()
    audit(
        db,
        None,
        admin.id,
        "admin.global_suppression_added",
        "suppression",
        suppression.id,
        {"email": email, "domain": domain},
    )
    db.commit()
    db.refresh(suppression)
    return suppression


@router.delete("/suppressions/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_global_suppression(
    suppression_id: int,
    db: Session = Depends(admin_db),
    admin: User = Depends(require_superuser),
) -> None:
    suppression = db.scalar(
        select(Suppression).where(
            Suppression.id == suppression_id, Suppression.workspace_id.is_(None)
        )
    )
    if suppression is None:
        raise NotFoundError("Suppression not found")
    db.delete(suppression)
    audit(
        db,
        None,
        admin.id,
        "admin.global_suppression_removed",
        "suppression",
        suppression_id,
        {"email": suppression.email, "domain": suppression.domain},
    )
    db.commit()


# --- admin audit trail ---------------------------------------------------------------------------


@router.get("/audit-logs", response_model=list[AdminAuditRow])
def admin_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(admin_db),
) -> list[AdminAuditRow]:
    rows = db.execute(
        select(AuditLog, User.email)
        .join(User, User.id == AuditLog.actor_id, isouter=True)
        .where(AuditLog.action.like("admin.%"))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    ).all()
    return [
        AdminAuditRow(
            id=log.id,
            created_at=log.created_at,
            workspace_id=log.workspace_id,
            actor_email=email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            metadata=log.metadata_,
        )
        for log, email in rows
    ]
