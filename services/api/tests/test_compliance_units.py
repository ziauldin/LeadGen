"""Unit tests for compliance outreach checks."""

from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.suppression import Suppression
from app.models.workspace import Workspace
from app.services.compliance.outreach import is_email_suppressed, validate_lead_for_outreach
from tests.conftest import TestingSessionLocal, setup_db


def _make_lead(**kwargs) -> Lead:
    defaults = {
        "workspace_id": 1,
        "niche_id": 1,
        "full_name": "Alex Morgan",
        "status": LeadStatus.QUALIFIED,
        "score": 80.0,
        "source_url": "https://example.com/listing",
        "compliance_source_note": "Public directory",
    }
    defaults.update(kwargs)
    return Lead(**defaults)


def test_validate_lead_for_outreach_requires_source_and_note():
    setup_db()
    db = TestingSessionLocal()
    try:
        lead = _make_lead(source_url=None, compliance_source_note=None, email_contacts=[])
        errors = validate_lead_for_outreach(lead, db)
        assert any("source URL" in err for err in errors)
        assert any("compliance" in err.lower() for err in errors)
        assert any("email contact" in err.lower() for err in errors)
    finally:
        db.close()


def test_suppression_matching_rules():
    setup_db()
    db = TestingSessionLocal()
    try:
        db.add_all(
            [
                Workspace(id=1, name="A", slug="a"),
                Workspace(id=2, name="B", slug="b"),
            ],
        )
        db.flush()
        db.add_all(
            [
                # An unsubscribe: blocks one address only.
                Suppression(workspace_id=1, email="blocked@example.com", reason="unsubscribe"),
                # A manual domain block.
                Suppression(workspace_id=1, email=None, domain="blocked-domain.com"),
                # Platform-wide hard bounce applies to every workspace.
                Suppression(workspace_id=None, email="bounced@elsewhere.com", reason="hard_bounce"),
                # Another workspace's suppression must not leak.
                Suppression(workspace_id=2, email="theirs@example.com"),
            ],
        )
        db.commit()

        assert is_email_suppressed(db, 1, "blocked@example.com") is True
        assert is_email_suppressed(db, 1, "BLOCKED@example.com") is True
        assert is_email_suppressed(db, 1, "colleague@example.com") is False
        assert is_email_suppressed(db, 1, "anyone@blocked-domain.com") is True
        assert is_email_suppressed(db, 1, "bounced@elsewhere.com") is True
        assert is_email_suppressed(db, 2, "bounced@elsewhere.com") is True
        assert is_email_suppressed(db, 1, "theirs@example.com") is False
        assert is_email_suppressed(db, 2, "theirs@example.com") is True
    finally:
        db.close()
