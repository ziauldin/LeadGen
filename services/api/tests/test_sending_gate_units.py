import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.campaign import Campaign
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import (
    CampaignStatus,
    EmailMessageStatus,
    LeadStatus,
    ProviderName,
    ProviderType,
    UserRole,
)
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.models.workspace import Workspace
from app.services.sending.gate import GateKind, evaluate_send_gate
from app.services.sending.schedule import schedule_for

# A Friday at 12:00 UTC.
FRIDAY_NOON = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _fixtures(db, **campaign_overrides):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        name="Gate User",
        email=f"gate-{suffix}@example.com",
        hashed_password="hash",
        role=UserRole.OPERATOR,
    )
    workspace = Workspace(name="Gate", slug=f"gate-{suffix}")
    db.add_all([user, workspace])
    db.flush()
    ws = workspace.id
    niche = Niche(workspace_id=ws, user_id=user.id, name="N", country="UK", industry="Food")
    db.add(niche)
    db.flush()
    campaign = Campaign(
        workspace_id=ws,
        niche_id=niche.id,
        name="Gate Campaign",
        status=CampaignStatus.ACTIVE,
        daily_send_limit=20,
        sending_window_start="09:00",
        sending_window_end="17:00",
        sending_days=[0, 1, 2, 3, 4],
        **campaign_overrides,
    )
    db.add(campaign)
    db.flush()
    lead = Lead(
        workspace_id=ws,
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
        EmailContact(workspace_id=ws, lead_id=lead.id, email="gate@example.com", is_personal=True)
    )
    message = EmailMessage(
        workspace_id=ws,
        campaign_id=campaign.id,
        lead_id=lead.id,
        recipient_email="gate@example.com",
        recipient_domain="example.com",
        subject="Hello",
        body="Body",
        status=EmailMessageStatus.APPROVED,
    )
    db.add(message)
    db.commit()
    for obj in (campaign, lead, message, workspace):
        db.refresh(obj)
    return campaign, lead, message, workspace


def _sent(db, campaign, lead, count, *, sent_at, domain="other.com", credential_id=None):
    for i in range(count):
        db.add(
            EmailMessage(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                lead_id=lead.id,
                recipient_email=f"p{i}-{uuid.uuid4().hex[:4]}@{domain}",
                recipient_domain=domain,
                subject="s",
                body="b",
                status=EmailMessageStatus.SENT,
                sent_at=sent_at,
                sender_credential_id=credential_id,
            ),
        )
    db.commit()


def test_allows_approved_message_in_window(db):
    campaign, lead, message, ws = _fixtures(db)
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.ALLOW


def test_unapproved_message_is_blocked(db):
    campaign, lead, message, ws = _fixtures(db)
    message.status = EmailMessageStatus.DRAFT
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.BLOCK
    assert any("not approved" in r.lower() for r in decision.reasons)


def test_missing_compliance_fields_block(db):
    campaign, lead, message, ws = _fixtures(db)
    lead.source_url = None
    lead.compliance_source_note = None
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.BLOCK
    assert any("source URL" in r for r in decision.reasons)


def test_paused_campaign_defers_not_fails(db):
    campaign, lead, message, ws = _fixtures(db)
    campaign.status = CampaignStatus.PAUSED
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.DEFER


def test_outside_window_defers_until_next_open(db):
    campaign, lead, message, ws = _fixtures(db)
    evening = FRIDAY_NOON.replace(hour=20)
    decision = evaluate_send_gate(db, campaign, message, lead, evening, workspace=ws)
    assert decision.kind == GateKind.DEFER
    # Friday evening -> next sending day is Monday 09:00.
    assert decision.retry_at == datetime(2026, 6, 29, 9, 0, tzinfo=UTC)


def test_window_uses_campaign_timezone(db):
    campaign, lead, message, ws = _fixtures(db, timezone="America/New_York")
    # 12:00 UTC is 08:00 in New York: before the 09:00 window opens.
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.DEFER
    assert decision.retry_at == datetime(2026, 6, 26, 13, 0, tzinfo=UTC)
    later = FRIDAY_NOON + timedelta(hours=2)
    assert evaluate_send_gate(db, campaign, message, lead, later, workspace=ws).allowed


def test_weekend_is_not_a_sending_day(db):
    campaign, lead, message, ws = _fixtures(db)
    saturday = FRIDAY_NOON + timedelta(days=1)
    decision = evaluate_send_gate(db, campaign, message, lead, saturday, workspace=ws)
    assert decision.kind == GateKind.DEFER


def test_daily_limit_defers_to_next_day(db):
    campaign, lead, message, ws = _fixtures(
        db,
    )
    campaign.daily_send_limit = 2
    _sent(db, campaign, lead, 2, sent_at=FRIDAY_NOON - timedelta(hours=1))
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.DEFER
    assert "daily send limit" in decision.reasons[0]
    assert decision.retry_at == datetime(2026, 6, 29, 9, 0, tzinfo=UTC)


def test_per_domain_limit_defers(db):
    campaign, lead, message, ws = _fixtures(db, per_domain_limit=1)
    _sent(db, campaign, lead, 1, sent_at=FRIDAY_NOON - timedelta(hours=1), domain="example.com")
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.DEFER
    assert "Per-domain" in decision.reasons[0]


def test_warmup_cap_defers(db):
    campaign, lead, message, ws = _fixtures(db)
    credential = ProviderCredential(
        workspace_id=ws.id,
        provider_type=ProviderType.EMAIL,
        provider_name=ProviderName.SMTP,
        display_name="SMTP",
        encrypted_config_json="",
        warmup_enabled=True,
        warmup_started_at=FRIDAY_NOON - timedelta(days=1),
        warmup_start_volume=2,
        warmup_daily_increment=1,
    )
    db.add(credential)
    db.commit()
    # Day 2 of warm-up: cap = 2 + 1 = 3.
    _sent(
        db, campaign, lead, 3, sent_at=FRIDAY_NOON - timedelta(hours=1), credential_id=credential.id
    )
    decision = evaluate_send_gate(
        db,
        campaign,
        message,
        lead,
        FRIDAY_NOON,
        workspace=ws,
        credential=credential,
    )
    assert decision.kind == GateKind.DEFER
    assert "Warm-up" in decision.reasons[0]


def test_monthly_send_quota_defers(db):
    from app.models.workspace import UsageCounter

    campaign, lead, message, ws = _fixtures(db)
    ws.plan_overrides = {"monthly_sends": 5}
    db.add(UsageCounter(workspace_id=ws.id, metric="monthly_sends", period_key="2026-06", count=5))
    db.commit()
    decision = evaluate_send_gate(db, campaign, message, lead, FRIDAY_NOON, workspace=ws)
    assert decision.kind == GateKind.DEFER
    assert decision.retry_at == datetime(2026, 7, 1, tzinfo=UTC)


def test_schedule_window_crossing_midnight(db):
    campaign, *_ = _fixtures(
        db,
    )
    campaign.sending_window_start = "22:00"
    campaign.sending_window_end = "02:00"
    campaign.sending_days = [0, 1, 2, 3, 4, 5, 6]
    schedule = schedule_for(campaign, None, None)
    assert schedule.is_open(datetime(2026, 6, 26, 23, 30, tzinfo=UTC))
    assert schedule.is_open(datetime(2026, 6, 27, 1, 0, tzinfo=UTC))
    assert not schedule.is_open(datetime(2026, 6, 27, 12, 0, tzinfo=UTC))
