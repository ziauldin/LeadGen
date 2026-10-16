"""Authentication for the public API: ``Authorization: Bearer lg_live_...``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.flags import feature_enabled
from app.core.permissions import permissions_for
from app.core.rate_limit import client_ip, enforce
from app.core.request_context import workspace_id_var
from app.core.tenancy import WorkspaceContext, bind_session, system_session
from app.models.developer import ApiKey, IdempotencyRecord
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.services.billing.plans import features_for
from app.services.developer.api_keys import SCOPES, find_key


@dataclass
class ApiContext:
    ctx: WorkspaceContext
    key: ApiKey


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_api_context(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiContext:
    scheme, _, raw = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not raw.strip():
        raise _unauthorized("Send your API key as: Authorization: Bearer <key>")
    key = find_key(db, raw.strip())
    if key is None:
        raise _unauthorized("Invalid, expired or revoked API key")

    with system_session(db):
        workspace = db.get(Workspace, key.workspace_id)
        member = (
            db.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == key.workspace_id,
                    WorkspaceMember.user_id == key.created_by_id,
                )
            )
            if key.created_by_id
            else None
        )
    if workspace is None or workspace.deleted_at is not None:
        raise _unauthorized("Invalid, expired or revoked API key")
    if not feature_enabled("public_api", workspace):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # A key stops working when the person who created it leaves the workspace.
    if member is None:
        raise _unauthorized("The person who created this key is no longer in the workspace")
    if not features_for(workspace).api_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API access isn't included in this workspace's plan",
        )
    enforce(settings.rate_limit_api, "api_key", str(key.id))

    bind_session(db, key.workspace_id)
    request.state.workspace_id = key.workspace_id
    workspace_id_var.set(key.workspace_id)
    now = datetime.now(UTC)
    last = key.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last is None or now - last > timedelta(minutes=1):
        key.last_used_at = now
        key.last_used_ip = client_ip(request)
        db.commit()

    custom = member.custom_role.permissions if member.custom_role else None
    ctx = WorkspaceContext(
        workspace_id=key.workspace_id,
        user_id=member.user_id,
        role=WorkspaceRole(member.role),
        workspace=workspace,
        permissions=permissions_for(member.role, custom),
    )
    return ApiContext(ctx=ctx, key=key)


def require_scope(scope: str) -> Callable[..., ApiContext]:
    """The key must carry ``scope`` and its creator must still hold the matching permission."""
    permission = SCOPES[scope][1]

    def dependency(api: ApiContext = Depends(get_api_context)) -> ApiContext:
        if scope not in (api.key.scopes or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This API key doesn't have the {scope} scope",
            )
        if permission and not api.ctx.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The key's owner no longer has permission for this",
            )
        return api

    return dependency


def idempotent(
    db: Session,
    api: ApiContext,
    key: str | None,
    request_body: Any,
    run: Callable[[], Any],
    *,
    status_code: int = 200,
) -> Any:
    """Run ``run`` once per Idempotency-Key; repeat calls get the stored response back."""
    if not key:
        return run()
    if len(key) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key is too long"
        )
    digest = hashlib.sha256(
        json.dumps(jsonable_encoder(request_body), sort_keys=True, default=str).encode()
    ).hexdigest()
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.api_key_id == api.key.id, IdempotencyRecord.key == key
        )
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This Idempotency-Key was already used with a different request",
            )
        return JSONResponse(
            status_code=existing.status_code,
            content=existing.response_body,
            headers={"Idempotent-Replayed": "true"},
        )
    result = run()
    db.add(
        IdempotencyRecord(
            workspace_id=api.ctx.workspace_id,
            api_key_id=api.key.id,
            key=key,
            request_hash=digest,
            status_code=status_code,
            response_body=jsonable_encoder(result),
        )
    )
    db.commit()
    return result
