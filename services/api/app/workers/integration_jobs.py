from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.integration import IntegrationConnection
from app.models.workspace import Workspace
from app.services.integrations import service


def _with_connection[T](
    connection_id: int, run: Callable[[Session, IntegrationConnection], T]
) -> T | None:
    db = SessionLocal()
    try:
        with system_session(db):  # find which workspace the connection belongs to
            connection = db.get(IntegrationConnection, connection_id)
            workspace = db.get(Workspace, connection.workspace_id) if connection else None
        if connection is None or workspace is None or not service.allowed(workspace):
            return None
        with workspace_scope(db, workspace.id):
            connection = db.get(IntegrationConnection, connection_id)
            return run(db, connection) if connection else None
    finally:
        db.close()


@celery_app.task(name="integrations.sync_object", acks_late=True, ignore_result=True)
def sync_integration_object(connection_id: int, object_type: str, local_id: int) -> str | None:
    return _with_connection(
        connection_id, lambda db, c: service.sync_object(db, c, object_type, local_id)
    )


@celery_app.task(name="integrations.sync_all", acks_late=True, ignore_result=True)
def sync_integration_all(connection_id: int) -> dict[str, int] | None:
    return _with_connection(connection_id, service.sync_all)


@celery_app.task(name="integrations.pull_statuses", ignore_result=True)
def pull_integration_statuses() -> int:
    """Every 15 minutes: close local deals that were won or lost in a connected CRM."""
    db = SessionLocal()
    try:
        with system_session(db):
            ids = list(
                db.scalars(
                    select(IntegrationConnection.id).where(IntegrationConnection.status == "active")
                ).all()
            )
    finally:
        db.close()
    moved = 0
    for connection_id in ids:
        moved += _with_connection(connection_id, service.pull_statuses) or 0
    return moved
