"""Data subject requests, workspace exports and retention settings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.api.paging import PageParams, page_params
from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.permissions import Permission
from app.core.storage import get_storage
from app.core.tenancy import WorkspaceContext
from app.models.privacy import DataRequest
from app.models.user import User
from app.models.workspace import WorkspaceSettings
from app.services.privacy.service import create_request
from app.services.workspaces.service import audit

router = APIRouter(prefix="/privacy", tags=["privacy"])


class DataRequestCreate(BaseModel):
    kind: Literal["export", "erase", "workspace_export"]
    email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=500)


class DataRequestRead(BaseModel):
    id: int
    kind: str
    status: str
    subject_email: str | None
    requested_by: str | None
    note: str | None
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    downloadable: bool
    summary: dict[str, int] | None
    error: str | None


class DataRequestPage(BaseModel):
    items: list[DataRequestRead]
    total: int
    skip: int
    limit: int


class DownloadRead(BaseModel):
    url: str


class GovernanceSettings(BaseModel):
    require_lia_note: bool = False
    retention_uncontacted_lead_days: int | None = Field(default=None, ge=30, le=3650)
    retention_reply_days: int | None = Field(default=None, ge=30, le=3650)


def _read(request: DataRequest, requested_by: str | None) -> DataRequestRead:
    now = datetime.now(UTC)
    expires = request.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return DataRequestRead(
        id=request.id,
        kind=request.kind,
        status=request.status,
        subject_email=request.subject_email,
        requested_by=requested_by,
        note=request.note,
        created_at=request.created_at,
        completed_at=request.completed_at,
        expires_at=request.expires_at,
        downloadable=bool(request.file_key and expires and expires > now),
        summary=request.summary,
        error=request.error,
    )


def _required_permission(kind: str) -> Permission:
    return Permission.DATA_EXPORT if kind == "workspace_export" else Permission.PRIVACY_MANAGE


@router.get("/requests", response_model=DataRequestPage)
def list_requests(
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DataRequestPage:
    """Requests this member may see: all of them with privacy.manage, else their own exports."""
    query = select(DataRequest, User.name).join(
        User, User.id == DataRequest.requested_by_id, isouter=True
    )
    query = query.where(DataRequest.workspace_id == ctx.workspace_id)
    if not ctx.can(Permission.PRIVACY_MANAGE):
        query = query.where(
            DataRequest.requested_by_id == ctx.user_id, DataRequest.kind == "workspace_export"
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(DataRequest.created_at.desc(), DataRequest.id.desc())
        .offset(page.skip)
        .limit(page.limit)
    ).all()
    return DataRequestPage(
        items=[_read(r, name) for r, name in rows], total=total, skip=page.skip, limit=page.limit
    )


@router.post("/requests", response_model=DataRequestRead, status_code=status.HTTP_201_CREATED)
def create_data_request(
    payload: DataRequestCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DataRequestRead:
    from fastapi import HTTPException

    from app.workers.privacy_jobs import process_data_request

    if not ctx.can(_required_permission(payload.kind)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Your role doesn't allow this request"
        )
    if payload.kind != "workspace_export" and not payload.email:
        raise ValidationFailedError("Enter the person's email address")
    request = create_request(
        db,
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        kind=payload.kind,
        email=payload.email,
        note=payload.note,
    )
    process_data_request.delay(request.id)
    db.refresh(request)
    user = db.get(User, ctx.user_id)
    return _read(request, user.name if user else None)


def _get(db: Session, ctx: WorkspaceContext, request_id: int) -> DataRequest:
    request = db.scalar(
        select(DataRequest).where(
            DataRequest.id == request_id, DataRequest.workspace_id == ctx.workspace_id
        )
    )
    if request is None:
        raise NotFoundError("Request not found")
    if not ctx.can(Permission.PRIVACY_MANAGE) and not (
        request.kind == "workspace_export" and request.requested_by_id == ctx.user_id
    ):
        raise NotFoundError("Request not found")
    return request


@router.post("/requests/{request_id}/download", response_model=DownloadRead)
def download_request(
    request_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DownloadRead:
    """A short-lived signed link to the export file."""
    request = _get(db, ctx, request_id)
    expires = request.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if not request.file_key or not expires or expires <= datetime.now(UTC):
        raise NotFoundError("This export has expired. Start a new one.")
    filename = f"leadsgen-{request.kind.replace('_', '-')}-{request.id}.zip"
    audit(
        db, ctx.workspace_id, ctx.user_id, "privacy.export_downloaded", "data_request", request.id
    )
    db.commit()
    return DownloadRead(
        url=get_storage().download_url(request.file_key, expires_in=900, filename=filename)
    )


@router.post("/requests/{request_id}/retry", response_model=DataRequestRead)
def retry_request(
    request_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DataRequestRead:
    from app.workers.privacy_jobs import process_data_request

    request = _get(db, ctx, request_id)
    if request.status != "failed":
        raise ValidationFailedError("Only failed requests can be retried")
    process_data_request.delay(request.id)
    db.refresh(request)
    return _read(request, None)


@router.get("/settings", response_model=GovernanceSettings)
def get_governance(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> GovernanceSettings:
    row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ctx.workspace_id)
    )
    if row is None:
        return GovernanceSettings()
    return GovernanceSettings(
        require_lia_note=row.require_lia_note,
        retention_uncontacted_lead_days=row.retention_uncontacted_lead_days,
        retention_reply_days=row.retention_reply_days,
    )


@router.put("/settings", response_model=GovernanceSettings)
def update_governance(
    payload: GovernanceSettings,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.PRIVACY_MANAGE)),
) -> GovernanceSettings:
    row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ctx.workspace_id)
    )
    if row is None:
        row = WorkspaceSettings(workspace_id=ctx.workspace_id)
        db.add(row)
    row.require_lia_note = payload.require_lia_note
    row.retention_uncontacted_lead_days = payload.retention_uncontacted_lead_days
    row.retention_reply_days = payload.retention_reply_days
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "privacy.settings_updated",
        "workspace",
        ctx.workspace_id,
        payload.model_dump(),
    )
    db.commit()
    return payload
