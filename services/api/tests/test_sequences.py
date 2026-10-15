from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.services.campaigns.sequences import advance_sequences
from app.services.sending.sender import dispatch
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import STEP, approved_message

STEPS = [
    STEP,
    {
        "step_number": 2,
        "delay_days": 3,
        "subject_template": "ignored when threading",
        "body_template": "Hi {{first_name}}, just bumping this.\n\nOpt out: {{unsubscribe_link}}",
    },
    {
        "step_number": 3,
        "delay_days": 4,
        "subject_template": "Last note",
        "body_template": "Closing the loop.\n\nIf this is not relevant, reply not relevant. "
        "{{unsubscribe_link}}",
    },
]


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _messages(db, campaign_id):
    return db.scalars(
        select(EmailMessage)
        .where(EmailMessage.campaign_id == campaign_id)
        .order_by(EmailMessage.step_number),
    ).all()


def _enrollment(db, campaign_id) -> CampaignEnrollment:
    return db.scalar(
        select(CampaignEnrollment).where(CampaignEnrollment.campaign_id == campaign_id)
    )


def test_follow_ups_are_drafted_after_the_delay_and_need_approval():
    client = get_client()
    headers, campaign_id, _ = approved_message(client, campaign_overrides={"steps": STEPS})
    db = _db()
    try:
        start = datetime.now(UTC)
        assert dispatch(db, now=start)["sent"] == 1
        enrollment = _enrollment(db, campaign_id)
        assert (enrollment.current_step, enrollment.next_step_number) == (1, 2)

        # Too early: nothing is drafted.
        assert advance_sequences(db, now=start + timedelta(hours=1))["created"] == 0

        # Within a day of the follow-up being due: a pending-approval draft appears.
        result = advance_sequences(db, now=start + timedelta(days=2, hours=12))
        assert result["created"] == 1
        follow_up = _messages(db, campaign_id)[1]
        follow_up_id = follow_up.id
        assert follow_up.status == EmailMessageStatus.PENDING_APPROVAL
        assert follow_up.step_number == 2
        assert follow_up.subject.startswith("Re: Quick question about")
        assert follow_up.scheduled_for is not None

        # Running the scheduler again never duplicates the draft.
        assert advance_sequences(db, now=start + timedelta(days=2, hours=13))["created"] == 0
    finally:
        db.close()

    approved = client.post(
        "/emails/approve",
        headers=headers,
        json={"email_message_id": follow_up_id},
    )
    assert approved.status_code == 200

    db = _db()
    try:
        # Not due yet: scheduled_for is in the future relative to "start".
        assert dispatch(db, now=start + timedelta(days=1))["sent"] == 0
        assert dispatch(db, now=start + timedelta(days=3, hours=1))["sent"] == 1
        sent = _messages(db, campaign_id)[1]
        assert sent.status == EmailMessageStatus.SENT
        assert _enrollment(db, campaign_id).next_step_number == 3
    finally:
        db.close()


def test_unsubscribe_stops_the_sequence():
    client = get_client()
    _headers, campaign_id, (message_id,) = approved_message(
        client, campaign_overrides={"steps": STEPS}
    )
    db = _db()
    try:
        start = datetime.now(UTC)
        dispatch(db, now=start)
        advance_sequences(db, now=start + timedelta(days=3))
        token = db.get(EmailMessage, message_id).unsubscribe_token
    finally:
        db.close()

    client.post(f"/unsubscribe/{token}")

    db = _db()
    try:
        enrollment = _enrollment(db, campaign_id)
        assert enrollment.status == "opted_out"
        assert enrollment.next_step_number is None
        assert _messages(db, campaign_id)[1].status == EmailMessageStatus.CANCELLED
        assert advance_sequences(db, now=start + timedelta(days=10))["created"] == 0
    finally:
        db.close()


def test_manual_stop_cancels_pending_steps():
    client = get_client()
    headers, campaign_id, _ = approved_message(client, campaign_overrides={"steps": STEPS})
    enrollment_id = client.get(f"/campaigns/{campaign_id}/enrollments", headers=headers).json()[
        "items"
    ][0]["id"]
    response = client.post(
        f"/campaigns/{campaign_id}/enrollments/{enrollment_id}/stop",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    db = _db()
    try:
        assert _messages(db, campaign_id)[0].status == EmailMessageStatus.CANCELLED
    finally:
        db.close()


def test_single_step_campaign_completes_after_grace_period():
    client = get_client()
    _headers, campaign_id, _ = approved_message(client)
    db = _db()
    try:
        start = datetime.now(UTC)
        dispatch(db, now=start)
        assert advance_sequences(db, now=start + timedelta(days=1))["completed_enrollments"] == 0
        result = advance_sequences(db, now=start + timedelta(days=4))
        assert result["completed_enrollments"] == 1
        assert result["completed_campaigns"] == 1
        campaign = db.get(Campaign, campaign_id)
        assert campaign.status == CampaignStatus.COMPLETED
        assert campaign.completed_at is not None
    finally:
        db.close()


def test_adding_the_same_lead_twice_is_skipped():
    client = get_client()
    headers, campaign_id, _ = approved_message(client)
    lead_id = client.get("/leads", headers=headers).json()["items"][0]["id"]
    again = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()
    assert again["created"] == 0
    assert again["skipped"] == 1
