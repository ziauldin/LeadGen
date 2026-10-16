import pytest
from sqlalchemy import select

from app.core.tenancy import TenantIsolationError, bind_session, system_session, workspace_scope
from app.models.niche import Niche
from app.models.workspace import Workspace
from tests.conftest import TestingSessionLocal, setup_db


def _two_workspaces(db):
    db.add_all([Workspace(id=1, name="A", slug="core-a"), Workspace(id=2, name="B", slug="core-b")])
    db.flush()
    db.add_all(
        [
            Niche(workspace_id=1, user_id=None, name="A niche", country="UK", industry="X"),
            Niche(workspace_id=2, user_id=None, name="B niche", country="UK", industry="X"),
        ],
    )
    db.commit()


def test_unfiltered_queries_are_scoped_automatically():
    setup_db()
    db = TestingSessionLocal()
    try:
        with system_session(db):
            _two_workspaces(db)
        bind_session(db, 1)
        # No explicit workspace filter: the safety net still hides workspace 2.
        names = db.scalars(select(Niche.name)).all()
        assert names == ["A niche"]
        assert db.get(Niche, 2) is None or db.get(Niche, 2).workspace_id == 1
    finally:
        db.close()


def test_new_rows_are_stamped_and_cross_tenant_writes_rejected():
    setup_db()
    db = TestingSessionLocal()
    try:
        with system_session(db):
            _two_workspaces(db)
        with workspace_scope(db, 1):
            niche = Niche(name="Stamped", country="UK", industry="X")
            db.add(niche)
            db.flush()
            assert niche.workspace_id == 1

            db.add(Niche(workspace_id=2, name="Sneaky", country="UK", industry="X"))
            with pytest.raises(TenantIsolationError):
                db.flush()
            db.rollback()
    finally:
        db.close()


def test_system_session_sees_everything():
    setup_db()
    db = TestingSessionLocal()
    try:
        with system_session(db):
            _two_workspaces(db)
            assert len(db.scalars(select(Niche)).all()) == 2
    finally:
        db.close()
