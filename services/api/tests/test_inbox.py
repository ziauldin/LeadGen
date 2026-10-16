from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.email_message import EmailMessage
from app.models.inbox import Conversation
from app.models.reply import Reply
from app.models.suppression import Suppression
from app.models.user import User
from app.services.inbox.service import wake_snoozed
from app.services.sending.mock_provider import MOCK_OUTBOX
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import approved_message


def _with_reply(client):
    headers, campaign_id, message_ids = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    return headers, campaign_id, message_ids


def test_replies_open_conversations_with_a_full_thread():
    client = get_client()
    headers, _campaign, message_ids = _with_reply(client)
    page = client.get("/inbox/conversations", headers=headers).json()
    assert page["total"] == 1
    assert page["counts"]["unread"] == 1
    row = page["items"][0]
    assert row["unread"] is True
    assert row["lead_name"] == "Person 0"
    assert row["contact_email"] == "alex@example-foods.co.uk"

    detail = client.get(f"/inbox/conversations/{row['id']}", headers=headers).json()
    assert [m["kind"] for m in detail["messages"]] == ["sent", "received"]
    assert detail["messages"][0]["id"] == message_ids[0]
    assert detail["can_reply"] is True
    # Opening it marks it read.
    assert client.get("/inbox/conversations", headers=headers).json()["counts"]["unread"] == 0


def test_assign_label_snooze_and_done():
    client = get_client()
    headers, _campaign, _ids = _with_reply(client)
    conversation_id = client.get("/inbox/conversations", headers=headers).json()["items"][0]["id"]
    db = TestingSessionLocal()
    try:
        me = db.scalar(select(User).where(User.email == "test@example.com")).id
    finally:
        db.close()

    updated = client.patch(
        f"/inbox/conversations/{conversation_id}",
        headers=headers,
        json={"assignee_id": me, "labels": ["pricing", " demo ", "pricing"]},
    ).json()
    assert updated["assignee_name"] == "Test User"
    assert updated["labels"] == ["demo", "pricing"]
    assert (
        client.get("/inbox/conversations", headers=headers, params={"assigned": "me"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        client.get("/inbox/conversations", headers=headers, params={"label": "demo"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        client.patch(
            f"/inbox/conversations/{conversation_id}", headers=headers, json={"assignee_id": 999999}
        ).status_code
        == 400
    )

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert (
        client.patch(
            f"/inbox/conversations/{conversation_id}", headers=headers, json={"snoozed_until": past}
        ).status_code
        == 400
    )
    soon = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    snoozed = client.patch(
        f"/inbox/conversations/{conversation_id}", headers=headers, json={"snoozed_until": soon}
    ).json()
    assert snoozed["status"] == "snoozed"
    assert client.get("/inbox/conversations", headers=headers).json()["total"] == 0
    assert (
        client.get("/inbox/conversations", headers=headers, params={"status": "snoozed"}).json()[
            "total"
        ]
        == 1
    )

    db = TestingSessionLocal()
    try:
        db.get(Conversation, conversation_id).snoozed_until = datetime.now(UTC) - timedelta(
            minutes=1
        )
        db.commit()
        assert wake_snoozed(db) == 1
    finally:
        db.close()
    assert client.get("/inbox/conversations", headers=headers).json()["items"][0]["unread"] is True

    client.patch(
        f"/inbox/conversations/{conversation_id}", headers=headers, json={"status": "done"}
    )
    assert (
        client.get("/inbox/conversations", headers=headers, params={"status": "done"}).json()[
            "total"
        ]
        == 1
    )


def test_reply_from_the_inbox_threads_through_the_original_sender():
    client = get_client()
    headers, campaign_id, _ids = _with_reply(client)
    conversation_id = client.get("/inbox/conversations", headers=headers).json()["items"][0]["id"]
    MOCK_OUTBOX.clear()
    sent = client.post(
        f"/inbox/conversations/{conversation_id}/reply",
        headers=headers,
        json={"body": "Great, how about Tuesday at 10?"},
    )
    assert sent.status_code == 200, sent.text
    outbound = MOCK_OUTBOX[-1]
    assert outbound.to == "alex@example-foods.co.uk"
    assert outbound.subject.lower().startswith("re:")
    assert outbound.headers["In-Reply-To"].startswith("<")
    db = TestingSessionLocal()
    try:
        message = db.get(EmailMessage, sent.json()["email_message_id"])
        assert message.status == "sent"
        assert message.generation_mode == "manual"
        assert message.campaign_id == campaign_id
    finally:
        db.close()
    detail = client.get(f"/inbox/conversations/{conversation_id}", headers=headers).json()
    assert [m["kind"] for m in detail["messages"]] == ["sent", "received", "sent"]


def test_no_replies_to_people_who_opted_out():
    client = get_client()
    headers, _campaign, _ids = _with_reply(client)
    conversation_id = client.get("/inbox/conversations", headers=headers).json()["items"][0]["id"]
    db = TestingSessionLocal()
    try:
        workspace_id = db.get(Conversation, conversation_id).workspace_id
        db.add(
            Suppression(
                workspace_id=workspace_id, email="alex@example-foods.co.uk", source="manual"
            )
        )
        db.commit()
    finally:
        db.close()
    blocked = client.post(
        f"/inbox/conversations/{conversation_id}/reply", headers=headers, json={"body": "Hi again"}
    )
    assert blocked.status_code == 400
    assert "not to be contacted" in blocked.json()["detail"]


def test_unmatched_replies_and_backfill():
    client = get_client()
    headers = auth_headers(client)
    db = TestingSessionLocal()
    try:
        workspace_id = db.scalar(
            select(User).where(User.email == "test@example.com")
        ).last_workspace_id
        db.add(
            Reply(
                workspace_id=workspace_id,
                from_email="Stranger@Elsewhere.co.uk",
                body="Who is this?",
                received_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()
    page = client.get("/inbox/conversations", headers=headers).json()  # backfills
    assert page["total"] == 1
    row = page["items"][0]
    assert row["lead_id"] is None and row["contact_email"] == "stranger@elsewhere.co.uk"
    detail = client.get(f"/inbox/conversations/{row['id']}", headers=headers).json()
    assert detail["can_reply"] is False
    assert (
        client.post(
            f"/inbox/conversations/{row['id']}/reply", headers=headers, json={"body": "Hi"}
        ).status_code
        == 400
    )


def test_ai_suggestions_need_ai_turned_on():
    client = get_client()
    headers, _campaign, _ids = _with_reply(client)
    conversation_id = client.get("/inbox/conversations", headers=headers).json()["items"][0]["id"]
    off = client.post(f"/inbox/conversations/{conversation_id}/suggest", headers=headers)
    assert off.status_code == 400
    client.patch(
        "/settings",
        headers=headers,
        json={"ai_mode": "assist", "product_description": "Quality software"},
    )
    suggestion = client.post(f"/inbox/conversations/{conversation_id}/suggest", headers=headers)
    assert suggestion.status_code == 200, suggestion.text
    assert suggestion.json()["body"]


def test_conversations_are_private_to_their_workspace():
    client = get_client()
    headers, _campaign, _ids = _with_reply(client)
    conversation_id = client.get("/inbox/conversations", headers=headers).json()["items"][0]["id"]
    other = auth_headers(client, "other@example.com")
    assert client.get(f"/inbox/conversations/{conversation_id}", headers=other).status_code == 404
    assert client.get("/inbox/conversations", headers=other).json()["total"] == 0
