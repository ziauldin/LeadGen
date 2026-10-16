"""Workspace (tenant) isolation.

Routes and services filter by workspace explicitly. As a second line of defence, any session
that has ``session.info["workspace_id"]`` set gets:

* a loader criterion on every SELECT/UPDATE/DELETE so ``TenantScoped`` rows from other
  workspaces are invisible, including relationship lazy-loads; and
* a ``before_flush`` check that stamps new tenant rows with the workspace and refuses to write
  rows that belong to a different workspace.

Background jobs that legitimately span workspaces (dispatchers, webhooks) must opt out
explicitly with :func:`system_session` / ``session.info["tenant_bypass"] = True``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import Connection, Select, event, select, text
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.errors import NotFoundError
from app.models.workspace import ROLE_RANK, TenantScoped, Workspace, WorkspaceRole

T = TypeVar("T")


class TenantIsolationError(RuntimeError):
    """A write tried to cross workspace boundaries. Always a programming error."""


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: int
    user_id: int
    role: WorkspaceRole
    workspace: Workspace

    def has_role(self, minimum: WorkspaceRole) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]


def _rls_settings(session: Session) -> tuple[str, str]:
    workspace_id = session.info.get("workspace_id")
    bypass = "on" if session.info.get("tenant_bypass") else "off"
    return (str(workspace_id) if workspace_id is not None else ""), bypass


def _apply_rls_settings(session: Session, connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    workspace_id, bypass = _rls_settings(session)
    connection.execute(
        text(
            "SELECT set_config('app.workspace_id', :ws, true), "
            "set_config('app.bypass_rls', :bypass, true)",
        ),
        {"ws": workspace_id, "bypass": bypass},
    )


def sync_rls(session: Session) -> None:
    """Push the session's tenant scope to PostgreSQL row-level security right away.

    New transactions pick it up in ``after_begin``; this covers scope changes made in the
    middle of a transaction.
    """
    if session.in_transaction():
        _apply_rls_settings(session, session.connection())


@event.listens_for(Session, "after_begin")
def _set_rls_on_begin(session: Session, _transaction: Any, connection: Connection) -> None:
    _apply_rls_settings(session, connection)


def bind_session(session: Session, workspace_id: int) -> None:
    session.info["workspace_id"] = workspace_id
    session.info.pop("tenant_bypass", None)
    sync_rls(session)


def unbind_session(session: Session) -> None:
    session.info.pop("workspace_id", None)
    sync_rls(session)


@contextmanager
def workspace_scope(session: Session, workspace_id: int) -> Iterator[Session]:
    """Temporarily scope a (system) session to one workspace."""
    previous = (session.info.get("workspace_id"), session.info.get("tenant_bypass"))
    bind_session(session, workspace_id)
    try:
        yield session
    finally:
        session.info["workspace_id"], session.info["tenant_bypass"] = previous
        if previous[0] is None:
            session.info.pop("workspace_id", None)
        if previous[1] is None:
            session.info.pop("tenant_bypass", None)
        sync_rls(session)


@contextmanager
def system_session(session: Session) -> Iterator[Session]:
    """Explicitly mark a session as cross-tenant (e.g. the send dispatcher)."""
    previous = session.info.get("workspace_id")
    previous_bypass = session.info.get("tenant_bypass")
    session.info.pop("workspace_id", None)
    session.info["tenant_bypass"] = True
    sync_rls(session)
    try:
        yield session
    finally:
        if not previous_bypass:
            session.info.pop("tenant_bypass", None)
        if previous is not None:
            session.info["workspace_id"] = previous
        sync_rls(session)


def scoped(stmt: Select[Any], model: type[TenantScoped], workspace_id: int) -> Select[Any]:
    return stmt.where(model.workspace_id == workspace_id)


def get_scoped_or_404[T](
    session: Session,
    model: type[T],
    object_id: int,
    workspace_id: int,
    *,
    label: str | None = None,
) -> T:
    obj: T | None = session.scalar(
        select(model).where(  # type: ignore[arg-type]
            model.id == object_id,  # type: ignore[attr-defined]
            model.workspace_id == workspace_id,  # type: ignore[attr-defined]
        ),
    )
    if obj is None:
        raise NotFoundError(f"{label or model.__name__} not found")
    return obj


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_criteria(state: ORMExecuteState) -> None:
    session = state.session
    workspace_id = session.info.get("workspace_id")
    if workspace_id is None or session.info.get("tenant_bypass"):
        return
    if not (state.is_select or state.is_update or state.is_delete):
        return
    if state.is_column_load:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.workspace_id == workspace_id,
            include_aliases=True,
        ),
    )


@event.listens_for(Session, "before_flush")
def _stamp_and_guard_tenant_rows(session: Session, _flush_context: Any, _instances: Any) -> None:
    workspace_id = session.info.get("workspace_id")
    if workspace_id is None or session.info.get("tenant_bypass"):
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped):
            current = getattr(obj, "workspace_id", None)
            if current is None:
                obj.workspace_id = workspace_id
            elif current != workspace_id:
                raise TenantIsolationError(
                    f"Refusing to create {type(obj).__name__} in workspace {current} "
                    f"from a session scoped to workspace {workspace_id}",
                )
    for obj in session.dirty:
        if isinstance(obj, TenantScoped) and getattr(obj, "workspace_id", None) != workspace_id:
            raise TenantIsolationError(
                f"Refusing to modify {type(obj).__name__} outside workspace {workspace_id}",
            )
