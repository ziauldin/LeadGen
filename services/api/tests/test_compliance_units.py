"""Unit tests for compliance outreach checks."""

from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.suppression import Suppression
from app.services.compliance.outreach import is_email_suppressed, validate_lead_for_outreach
from tests.conftest import TestingSessionLocal


def _make_lead(**kwargs) -> Lead:
    defaults = {
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
    db = TestingSessionLocal()
    try:
        lead = _make_lead(source_url=None, compliance_source_note=None, email_contacts=[])
        errors = validate_lead_for_outreach(lead, db)
        assert any("source URL" in err for err in errors)
        assert any("compliance" in err.lower() for err in errors)
        assert any("email contact" in err.lower() for err in errors)
    finally:
        db.close()


def test_is_email_suppressed_by_email_and_domain():
    db = TestingSessionLocal()
    try:
        db.add(
            Suppression(
                email="blocked@example.com",
                domain="example.com",
                reason="manual",
                source="test",
            ),
        )
        db.commit()

        assert is_email_suppressed(db, "blocked@example.com") is True
        assert is_email_suppressed(db, "other@example.com") is True
        assert is_email_suppressed(db, "safe@another.com") is False
    finally:
        db.rollback()
        db.close()
