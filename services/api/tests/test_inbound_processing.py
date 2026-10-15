from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.models.reply import Reply
from app.models.suppression import Suppression
from app.services.campaigns.sequences import advance_sequences
from app.services.inbound import normalize
from app.services.inbound.normalize import DeliveryEvent, InboundEmail
from app.services.inbound.processor import process_delivery_event, process_inbound_email
from app.services.inbound.text import strip_quoted
from app.services.sending.sender import dispatch
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import STEP, approved_message

TWO_STEPS = [
    STEP,
    {
        "step_number": 2,
        "delay_days": 2,
        "subject_template": "x",
        "body_template": "Bumping this. Opt out: {{unsubscribe_link}}",
    },
]


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _sent_campaign(client, **overrides):
    headers, campaign_id, message_ids = approved_message(
        client,
        campaign_overrides={"steps": TWO_STEPS, **overrides},
    )
    db = _db()
    try:
        start = datetime.now(UTC)
        dispatch(db, now=start)
        advance_sequences(db, now=start + timedelta(days=2))
        message = db.get(EmailMessage, message_ids[0])
        return (
            headers,
            campaign_id,
            message.id,
            message.workspace_id,
            message.rfc_message_id,
            message.reply_token,
        )
    finally:
        db.close()


def _reply(**kwargs) -> InboundEmail:
    defaults = {
        "from_email": "alex@example-foods.co.uk",
        "to": ["sam@acme.example"],
        "subject": "Re: Quick question",
        "text": "Sounds good, happy to chat on Tuesday.\n\nOn Mon, Sam wrote:\n> Hi Alex",
        "message_id": "reply-1@client.example",
    }
    defaults.update(kwargs)
    return InboundEmail(**defaults)


def _enrollment(db, campaign_id):
    return db.scalar(
        select(CampaignEnrollment).where(CampaignEnrollment.campaign_id == campaign_id)
    )


def test_strip_quoted_keeps_only_new_text():
    text = "Yes please.\n\nOn Tue, 1 Oct 2026 at 10:00, Sam <sam@acme.example> wrote:\n> old"
    assert strip_quoted(text) == "Yes please."
    assert strip_quoted("Thanks\n-- \nJo Bloggs\nCEO") == "Thanks"


def test_human_reply_matched_by_in_reply_to_stops_the_sequence():
    client = get_client()
    _h, campaign_id, message_id, ws, rfc_id, _token = _sent_campaign(client)
    db = _db()
    try:
        reply = process_inbound_email(db, ws, _reply(in_reply_to=rfc_id))
        assert reply.match_method == "in_reply_to"
        assert reply.email_message_id == message_id
        assert reply.classification == "positive"
        assert reply.body == "Sounds good, happy to chat on Tuesday."
        enrollment = _enrollment(db, campaign_id)
        assert enrollment.status == "replied"
        follow_up = db.scalar(
            select(EmailMessage).where(
                EmailMessage.enrollment_id == enrollment.id,
                EmailMessage.step_number == 2,
            ),
        )
        assert follow_up.status == EmailMessageStatus.CANCELLED
        # The same reply delivered twice is stored once.
        again = process_inbound_email(db, ws, _reply(in_reply_to=rfc_id))
        assert again.id == reply.id
    finally:
        db.close()


def test_reply_token_address_matches_when_headers_are_missing():
    client = get_client()
    _h, _campaign_id, message_id, ws, _rfc, token = _sent_campaign(client)
    db = _db()
    try:
        reply = process_inbound_email(
            db,
            ws,
            _reply(from_email="someone.else@forwarded.example", to=[f"reply+{token}@in.example"]),
        )
        assert reply.match_method == "reply_token"
        assert reply.email_message_id == message_id
    finally:
        db.close()


def test_out_of_office_does_not_stop_the_sequence():
    client = get_client()
    _h, campaign_id, _mid, ws, rfc_id, _t = _sent_campaign(client)
    db = _db()
    try:
        reply = process_inbound_email(
            db,
            ws,
            _reply(
                subject="Automatic reply: Quick question",
                text="I am out of the office until Monday with limited access to email.",
                headers={"Auto-Submitted": "auto-replied"},
                in_reply_to=rfc_id,
                message_id="ooo-1@client.example",
            ),
        )
        assert reply.classification == "out_of_office"
        assert reply.is_auto_reply is True
        assert _enrollment(db, campaign_id).status == "active"
    finally:
        db.close()


def test_unsubscribe_reply_suppresses_the_address():
    client = get_client()
    _h, campaign_id, _mid, ws, rfc_id, _t = _sent_campaign(client)
    db = _db()
    try:
        process_inbound_email(
            db,
            ws,
            _reply(text="Please remove me from your list.", in_reply_to=rfc_id, message_id="u@x"),
        )
        suppression = db.scalar(select(Suppression).where(Suppression.workspace_id == ws))
        assert suppression.email == "alex@example-foods.co.uk"
        assert suppression.reason_code == "reply_opt_out"
        assert _enrollment(db, campaign_id).status == "opted_out"
    finally:
        db.close()


def test_hard_bounce_marks_message_and_suppresses_platform_wide():
    client = get_client()
    _h, campaign_id, message_id, ws, _rfc, _t = _sent_campaign(client)
    db = _db()
    try:
        result = process_delivery_event(
            db,
            ws,
            DeliveryEvent(
                kind=normalize.BOUNCE_HARD,
                provider="resend",
                event_id="b1",
                recipient="alex@example-foods.co.uk",
                correlation_id=str(message_id),
                reason="Mailbox does not exist",
            ),
        )
        assert result == "hard_bounce"
        message = db.get(EmailMessage, message_id)
        assert message.status == EmailMessageStatus.BOUNCED
        assert message.bounce_status == "hard"
        platform = db.scalar(select(Suppression).where(Suppression.workspace_id.is_(None)))
        assert platform.email == "alex@example-foods.co.uk"
        assert platform.reason_code == "hard_bounce"
        assert _enrollment(db, campaign_id).status == "bounced"
    finally:
        db.close()


def test_complaint_suppresses_and_three_soft_bounces_suppress():
    client = get_client()
    _h, _cid, message_id, ws, _rfc, _t = _sent_campaign(client)
    db = _db()
    try:
        for i in range(2):
            process_delivery_event(
                db,
                ws,
                DeliveryEvent(
                    kind=normalize.BOUNCE_SOFT,
                    provider="x",
                    event_id=f"s{i}",
                    recipient="soft@x.co",
                ),
            )
        assert db.scalar(select(Suppression).where(Suppression.email == "soft@x.co")) is None
        process_delivery_event(
            db,
            ws,
            DeliveryEvent(
                kind=normalize.BOUNCE_SOFT, provider="x", event_id="s3", recipient="soft@x.co"
            ),
        )
        assert db.scalar(select(Suppression).where(Suppression.email == "soft@x.co")) is not None

        process_delivery_event(
            db,
            ws,
            DeliveryEvent(
                kind=normalize.COMPLAINT,
                provider="x",
                event_id="c1",
                correlation_id=str(message_id),
            ),
        )
        assert db.get(EmailMessage, message_id).status == EmailMessageStatus.COMPLAINED
        codes = {s.reason_code for s in db.scalars(select(Suppression)).all()}
        assert "complaint" in codes
    finally:
        db.close()


def test_unmatched_reply_can_be_linked_by_hand():
    client = get_client()
    headers, campaign_id, message_id, ws, _rfc, _t = _sent_campaign(client)
    db = _db()
    try:
        reply = process_inbound_email(
            db,
            ws,
            _reply(from_email="stranger@elsewhere.example", message_id="lost@x"),
        )
        assert reply.email_message_id is None
        assert reply.match_method == "unmatched"
        reply_id = reply.id
    finally:
        db.close()

    unmatched = client.get("/replies?classification=unmatched", headers=headers).json()
    assert [r["id"] for r in unmatched["items"]] == [reply_id]
    linked = client.post(
        f"/replies/{reply_id}/link",
        headers=headers,
        json={"email_message_id": message_id},
    )
    assert linked.status_code == 200
    assert linked.json()["match_method"] == "manual"
    detail = client.get(f"/replies/{reply_id}", headers=headers).json()
    assert detail["thread"][0]["id"] == message_id
    db = _db()
    try:
        assert _enrollment(db, campaign_id).status == "replied"
    finally:
        db.close()


def test_mailto_unsubscribe_and_bounce_report_emails():
    client = get_client()
    _h, _cid, message_id, ws, _rfc, _t = _sent_campaign(client)
    db = _db()
    try:
        token = db.get(EmailMessage, message_id).unsubscribe_token
        assert process_inbound_email(db, ws, _reply(to=[f"unsubscribe+{token}@in.example"])) is None
        assert db.scalar(select(Suppression).where(Suppression.workspace_id == ws)) is not None
    finally:
        db.close()

    client2 = get_client()
    _h, _cid, message_id, ws, rfc_id, _t = _sent_campaign(client2)
    db = _db()
    try:
        bounce = _reply(
            from_email="mailer-daemon@mx.example",
            subject="Undelivered Mail Returned to Sender",
            text="The following address failed",
            in_reply_to=rfc_id,
            failed_recipients=["alex@example-foods.co.uk"],
            message_id="dsn-1@mx",
        )
        assert process_inbound_email(db, ws, bounce) is None
        assert db.get(EmailMessage, message_id).status == EmailMessageStatus.BOUNCED
        assert db.scalar(select(Reply)) is None
    finally:
        db.close()


def test_bounce_spike_pauses_the_campaign():
    from app.services.inbound import processor

    client = get_client()
    _h, campaign_id, message_id, ws, _rfc, _t = _sent_campaign(client)
    original = processor.SAFETY_MIN_SENDS
    processor.SAFETY_MIN_SENDS = 1
    db = _db()
    try:
        process_delivery_event(
            db,
            ws,
            DeliveryEvent(
                kind=normalize.BOUNCE_HARD,
                provider="x",
                event_id="spike",
                correlation_id=str(message_id),
            ),
        )
        from app.models.campaign import Campaign

        campaign = db.get(Campaign, campaign_id)
        assert campaign.status == CampaignStatus.PAUSED
        assert "Paused automatically" in campaign.auto_paused_reason
    finally:
        processor.SAFETY_MIN_SENDS = original
        db.close()


def test_simulated_reply_goes_through_the_real_pipeline():
    client = get_client()
    headers, campaign_id, _mid, _ws, _rfc, _t = _sent_campaign(client)
    synced = client.post("/replies/sync", headers=headers).json()
    assert synced["synced"] == 1
    replies = client.get("/replies", headers=headers).json()["items"]
    assert replies[0]["match_method"] == "in_reply_to"
    db = _db()
    try:
        assert _enrollment(db, campaign_id).status == "replied"
    finally:
        db.close()
