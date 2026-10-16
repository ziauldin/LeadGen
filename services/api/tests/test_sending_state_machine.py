from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import update

from app.core.tenancy import system_session
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.services.sending.base import SendKind, SendResult
from app.services.sending.sender import deliver_message, dispatch, reap_stuck_messages
from app.services.sending.state import InvalidTransitionError, transition
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import approved_message, load_message

MOCK_SEND = "app.services.sending.mock_provider.MockEmailSender.send"


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def test_dispatch_sends_and_records_identifiers():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        counts = dispatch(db)
    finally:
        db.close()
    assert counts["sent"] == 1
    message = load_message(message_id)
    assert message.status == EmailMessageStatus.SENT
    assert message.rfc_message_id and message.rfc_message_id.startswith("lg.")
    assert message.reply_token
    assert message.provider_message_id
    assert message.send_attempts == 1


def test_a_message_is_claimed_only_once():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        db.execute(
            update(EmailMessage)
            .where(EmailMessage.id == message_id)
            .values(status=EmailMessageStatus.QUEUED),
        )
        db.commit()
        with patch(
            MOCK_SEND, return_value=SendResult(kind=SendKind.OK, provider_message_id="x")
        ) as send:
            first = deliver_message(db, message_id)
            second = deliver_message(db, message_id)  # duplicate task / retry
        assert (first, second) == ("sent", "skipped")
        assert send.call_count == 1
    finally:
        db.close()


def test_outside_window_defers_and_keeps_message_approved():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(
        client,
        campaign_overrides={"sending_window_start": "09:00", "sending_window_end": "10:00"},
    )
    db = _db()
    try:
        night = datetime.now(UTC).replace(hour=23, minute=30)
        db.execute(
            update(EmailMessage)
            .where(EmailMessage.id == message_id)
            .values(status=EmailMessageStatus.QUEUED),
        )
        db.commit()
        assert deliver_message(db, message_id, now=night) == "deferred"
    finally:
        db.close()
    message = load_message(message_id)
    assert message.status == EmailMessageStatus.APPROVED
    assert message.next_attempt_at is not None
    assert message.send_attempts == 0


def test_transient_errors_retry_with_backoff_then_fail():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        transient = SendResult(kind=SendKind.TRANSIENT, error="HTTP 503")
        with patch(MOCK_SEND, return_value=transient):
            outcomes = []
            for _ in range(5):
                db.execute(
                    update(EmailMessage)
                    .where(EmailMessage.id == message_id)
                    .values(status=EmailMessageStatus.QUEUED),
                )
                db.commit()
                outcomes.append(deliver_message(db, message_id))
        assert outcomes == ["retry", "retry", "retry", "retry", "failed"]
    finally:
        db.close()
    message = load_message(message_id)
    assert message.status == EmailMessageStatus.FAILED
    assert "attempts" in message.failure_reason


def test_retry_waits_for_next_attempt_time():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        with patch(MOCK_SEND, return_value=SendResult(kind=SendKind.TRANSIENT, error="429")):
            dispatch(db)
        assert load_message(message_id).status == EmailMessageStatus.APPROVED
        # Not due yet: the next dispatch must not pick it up.
        with patch(MOCK_SEND) as send:
            dispatch(db)
            assert send.call_count == 0
    finally:
        db.close()


def test_permanent_errors_fail_immediately():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        with patch(MOCK_SEND, return_value=SendResult(kind=SendKind.PERMANENT, error="HTTP 422")):
            counts = dispatch(db)
    finally:
        db.close()
    assert counts["failed"] == 1
    assert load_message(message_id).status == EmailMessageStatus.FAILED


def test_suppressed_recipient_is_cancelled_not_sent():
    client = get_client()
    headers, _campaign_id, (message_id,) = approved_message(client)
    client.post("/suppressions", headers=headers, json={"email": "alex@example-foods.co.uk"})
    message = load_message(message_id)
    # Adding a suppression cancels nothing by itself; the gate blocks at send time.
    assert message.status == EmailMessageStatus.APPROVED
    db = _db()
    try:
        with patch(MOCK_SEND) as send:
            dispatch(db)
            assert send.call_count == 0
    finally:
        db.close()
    assert load_message(message_id).status == EmailMessageStatus.CANCELLED


def test_daily_capacity_limits_dispatch():
    client = get_client()
    _headers, _campaign_id, message_ids = approved_message(
        client,
        emails=[f"p{i}@company-{i}.co.uk" for i in range(4)],
        campaign_overrides={"daily_send_limit": 2},
    )
    db = _db()
    try:
        counts = dispatch(db)
    finally:
        db.close()
    assert counts["sent"] == 2
    statuses = sorted(str(load_message(mid).status) for mid in message_ids)
    assert statuses == ["approved", "approved", "sent", "sent"]


def test_reaper_requeues_stuck_queued_and_fails_stuck_sending():
    client = get_client()
    _headers, _campaign_id, message_ids = approved_message(
        client,
        emails=["a@company-0.co.uk", "b@company-1.co.uk"],
    )
    old = datetime.now(UTC) - timedelta(hours=1)
    db = _db()
    try:
        db.execute(
            update(EmailMessage)
            .where(EmailMessage.id == message_ids[0])
            .values(status=EmailMessageStatus.QUEUED, queued_at=old),
        )
        db.execute(
            update(EmailMessage)
            .where(EmailMessage.id == message_ids[1])
            .values(status=EmailMessageStatus.SENDING, sending_started_at=old),
        )
        db.commit()
        assert reap_stuck_messages(db) == {"requeued": 1, "failed": 1}
    finally:
        db.close()
    assert load_message(message_ids[0]).status == EmailMessageStatus.APPROVED
    stuck = load_message(message_ids[1])
    assert stuck.status == EmailMessageStatus.FAILED
    assert "Unknown outcome" in stuck.failure_reason


def test_illegal_transitions_are_rejected():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    db = _db()
    try:
        with system_session(db):
            message = db.get(EmailMessage, message_id)
            transition(db, message, EmailMessageStatus.CANCELLED)
            with pytest.raises(InvalidTransitionError):
                transition(db, message, EmailMessageStatus.SENT)
    finally:
        db.close()


def test_process_sends_endpoint_is_scoped_to_one_campaign():
    client = get_client()
    headers, campaign_id, (message_id,) = approved_message(client)
    response = client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    assert response.status_code == 200
    assert response.json()["sent"] == 1
    assert load_message(message_id).status == EmailMessageStatus.SENT
