import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.campaign import Campaign
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus, UserRole
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.services.sending.gate import evaluate_send_gate


def _make_gate_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_gate_fixtures(db):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        name="Gate User",
        email=f"gate-user-{suffix}@example.com",
        hashed_password="hash",
        role=UserRole.OPERATOR,
    )
    db.add(user)
    db.flush()

    niche = Niche(
        user_id=user.id,
        name=f"Gate Niche {suffix}",
        country="UK",
        industry="Food Manufacturing",
        target_roles=["Quality Manager"],
        keywords=["governance"],
        exclusion_keywords=[],
    )
    db.add(niche)
    db.flush()

    campaign = Campaign(
        niche_id=niche.id,
        name="Gate Campaign",
        status=CampaignStatus.ACTIVE,
        daily_send_limit=20,
        sending_window_start="00:00",
        sending_window_end="23:59",
    )
    db.add(campaign)
    db.flush()

    lead = Lead(
        niche_id=niche.id,
        full_name="Gate Lead",
        status=LeadStatus.READY_FOR_OUTREACH,
        score=80.0,
        source_url="https://example.com/listing",
        compliance_source_note="Public listing",
    )
    db.add(lead)
    db.flush()

    db.add(
        EmailContact(
            lead_id=lead.id,
            email="gate@example.com",
            is_personal=True,
        ),
    )

    message = EmailMessage(
        campaign_id=campaign.id,
        lead_id=lead.id,
        recipient_email="gate@example.com",
        subject="Hello",
        body="Body",
        status=EmailMessageStatus.APPROVED,
    )
    db.add(message)
    db.commit()
    db.refresh(campaign)
    db.refresh(lead)
    db.refresh(message)
    return campaign, lead, message


def test_send_gate_allows_approved_message_in_active_campaign():
    db = _make_gate_db()
    try:
        campaign, lead, message = _seed_gate_fixtures(db)
        result = evaluate_send_gate(
            db,
            campaign,
            message,
            lead,
            now=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        assert result.allowed is True
        assert result.reasons == []
    finally:
        db.close()


def test_send_gate_blocks_unapproved_message():
    db = _make_gate_db()
    try:
        campaign, lead, message = _seed_gate_fixtures(db)
        message.status = EmailMessageStatus.DRAFT
        db.commit()

        result = evaluate_send_gate(
            db,
            campaign,
            message,
            lead,
            now=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        assert result.allowed is False
        assert any("not approved" in reason.lower() for reason in result.reasons)
    finally:
        db.close()


def test_send_gate_blocks_paused_campaign():
    db = _make_gate_db()
    try:
        campaign, lead, message = _seed_gate_fixtures(db)
        campaign.status = CampaignStatus.PAUSED
        db.commit()

        result = evaluate_send_gate(
            db,
            campaign,
            message,
            lead,
            now=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        assert result.allowed is False
        assert any("not active" in reason.lower() for reason in result.reasons)
    finally:
        db.close()


def test_send_gate_blocks_missing_compliance_fields():
    db = _make_gate_db()
    try:
        campaign, lead, message = _seed_gate_fixtures(db)
        lead.source_url = None
        lead.compliance_source_note = None
        db.commit()

        result = evaluate_send_gate(
            db,
            campaign,
            message,
            lead,
            now=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        assert result.allowed is False
        assert any("source URL" in reason for reason in result.reasons)
        assert any("compliance" in reason.lower() for reason in result.reasons)
    finally:
        db.close()
