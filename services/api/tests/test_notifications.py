from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.notification import LifecycleEmail, Notification
from app.models.user import User
from app.models.workspace import Workspace
from app.services.notifications import lifecycle, slack
from app.services.notifications.service import notify
from app.services.platform_email.mailer import OUTBOX
from tests.conftest import TestingSessionLocal, auth_headers, get_client, register_user


def _user(email="test@example.com"):
    db = TestingSessionLocal()
    try:
        return db.scalar(select(User).where(User.email == email))
    finally:
        db.close()


def _notify(kind, title, **kwargs):
    db = TestingSessionLocal()
    try:
        workspace_id = _user().last_workspace_id
        count = notify(db, workspace_id, kind, title, **kwargs)
        db.commit()
        return count
    finally:
        db.close()


def test_bell_lists_and_marks_read():
    client = get_client()
    headers = auth_headers(client)
    _notify(
        "positive_reply", "Jo replied: interested", body="Sounds good, call me", link="/replies/1"
    )
    _notify("member_joined", "Sam joined the workspace")
    listing = client.get("/notifications", headers=headers).json()
    assert listing["unread"] == 2
    assert [n["title"] for n in listing["items"]] == [
        "Sam joined the workspace",
        "Jo replied: interested",
    ]

    first = listing["items"][1]["id"]
    client.post("/notifications/read", headers=headers, json={"ids": [first]})
    assert client.get("/notifications", headers=headers).json()["unread"] == 1
    client.post("/notifications/read", headers=headers, json={"all": True})
    assert client.get("/notifications", headers=headers, params={"unread_only": True}).json() == {
        "items": [],
        "unread": 0,
    }


def test_notifications_are_private_to_each_person():
    client = get_client()
    owner = auth_headers(client)
    other = auth_headers(client, "other@example.com")
    _notify("positive_reply", "For the owner")
    assert client.get("/notifications", headers=other).json()["unread"] == 0
    owner_id = client.get("/notifications", headers=owner).json()["items"][0]["id"]
    client.post("/notifications/read", headers=other, json={"ids": [owner_id]})
    assert client.get("/notifications", headers=owner).json()["unread"] == 1


def test_preferences_control_channels():
    client = get_client()
    headers = auth_headers(client)
    prefs = {p["key"]: p for p in client.get("/notifications/preferences", headers=headers).json()}
    assert prefs["positive_reply"] == {
        "key": "positive_reply",
        "label": prefs["positive_reply"]["label"],
        "in_app": True,
        "email": True,
    }

    OUTBOX.clear()
    _notify("positive_reply", "Jo is interested")
    assert [m.subject for m in OUTBOX if m.tags.get("kind") == "notify:positive_reply"] == [
        "Jo is interested"
    ]

    saved = client.put(
        "/notifications/preferences",
        headers=headers,
        json={"settings": {"positive_reply": {"email": False, "in_app": False}}},
    )
    assert saved.status_code == 200
    OUTBOX.clear()
    assert _notify("positive_reply", "Another reply") == 0
    assert not [m for m in OUTBOX if m.tags.get("kind") == "notify:positive_reply"]
    assert (
        client.put(
            "/notifications/preferences",
            headers=headers,
            json={"settings": {"bogus": {"email": True}}},
        ).status_code
        == 400
    )


def test_role_targeting():
    from app.services.platform_email.mailer import OUTBOX as outbox

    client = get_client()
    owner = auth_headers(client)
    db = TestingSessionLocal()
    try:
        db.get(Workspace, _user().last_workspace_id).plan = "pro"
        db.commit()
    finally:
        db.close()
    client.post(
        "/workspaces/current/invitations",
        headers=owner,
        json={"email": "member@example.com", "role": "member"},
    )
    token = next(
        m.text.split("/invite/")[1].split()[0]
        for m in reversed(outbox)
        if m.to == "member@example.com"
    )
    member = auth_headers(client, "member@example.com")
    workspace_id = client.post(f"/invitations/{token}/accept", headers=member).json()["id"]
    member = {**member, "X-Workspace-Id": str(workspace_id)}

    # Billing problems go to owners only; interested replies to everyone.
    _notify("payment_failed", "Payment failed")
    _notify("positive_reply", "New interested reply")
    assert [n["title"] for n in client.get("/notifications", headers=member).json()["items"]] == [
        "New interested reply"
    ]
    # The owner also hears that the member joined.
    assert client.get("/notifications", headers=owner).json()["unread"] == 3


def test_positive_replies_notify_the_team():
    from tests.sending_helpers import approved_message

    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    replies = client.get("/replies", headers=headers).json()["items"]
    positive = [r for r in replies if r["classification"] == "positive"]
    titles = [n["title"] for n in client.get("/notifications", headers=headers).json()["items"]]
    assert len([t for t in titles if "replied with interest" in t]) == len(positive) >= 1


def test_slack_connection(monkeypatch):
    sent = []
    monkeypatch.setattr(slack, "send", lambda row, text: (sent.append(text) or True, None))
    client = get_client()
    headers = auth_headers(client)
    assert (
        client.put(
            "/workspaces/current/slack",
            headers=headers,
            json={"webhook_url": "https://evil.example/hook"},
        ).status_code
        == 400
    )
    connected = client.put(
        "/workspaces/current/slack",
        headers=headers,
        json={"webhook_url": "https://hooks.slack.com/services/T0/B0/XYZ"},
    ).json()
    assert connected["connected"] is True
    assert set(connected["events"]) == {
        "positive_reply",
        "campaign_paused",
        "payment_failed",
        "member_joined",
    }
    assert client.post("/workspaces/current/slack/test", headers=headers).status_code == 200
    assert "connected" in sent[0]

    _notify("positive_reply", "Jo is interested", link="/replies/9")
    assert any("Jo is interested" in text for text in sent)

    narrowed = client.put(
        "/workspaces/current/slack", headers=headers, json={"events": ["payment_failed"]}
    ).json()
    assert narrowed["events"] == ["payment_failed"]
    sent.clear()
    _notify("positive_reply", "Not posted")
    assert sent == []
    assert (
        client.put("/workspaces/current/slack", headers=headers, json={"disconnect": True}).json()[
            "connected"
        ]
        is False
    )


def test_welcome_email_once_on_verification():
    client = get_client()
    OUTBOX.clear()
    register_user(client)
    welcomes = [m for m in OUTBOX if m.tags.get("kind") == "lifecycle:welcome"]
    assert len(welcomes) == 1
    db = TestingSessionLocal()
    try:
        assert (
            lifecycle.send_welcome(
                db, db.scalar(select(User).where(User.email == "test@example.com"))
            )
            is False
        )
    finally:
        db.close()


def test_verification_reminder_and_trial_ending():
    client = get_client()
    register_user(client, "slow@example.com", verify=False)
    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "slow@example.com"))
        user.created_at = datetime.now(UTC) - timedelta(hours=30)
        workspace = db.get(Workspace, user.last_workspace_id)
        workspace.plan = "starter"
        workspace.trial_ends_at = datetime.now(UTC) + timedelta(days=2)
        db.commit()
        OUTBOX.clear()
        assert lifecycle.send_verification_reminders(db) == 1
        assert lifecycle.send_verification_reminders(db) == 0  # only once
        assert [m.tags.get("kind") for m in OUTBOX] == ["verify"]
        assert lifecycle.notify_trials_ending(db) == 1
        assert lifecycle.notify_trials_ending(db) == 0
        assert (
            db.scalar(select(Notification).where(Notification.kind == "trial_ending")) is not None
        )
    finally:
        db.close()


@pytest.mark.parametrize("opted_out", [False, True])
def test_weekly_digest(opted_out):
    from tests.sending_helpers import approved_message

    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    if opted_out:
        client.put(
            "/notifications/preferences",
            headers=headers,
            json={"settings": {"weekly_digest": {"email": False}}},
        )
    db = TestingSessionLocal()
    try:
        OUTBOX.clear()
        sent = lifecycle.weekly_digest(db)
        assert sent == (0 if opted_out else 1)
        if not opted_out:
            digest = next(m for m in OUTBOX if m.tags.get("kind") == "lifecycle:digest")
            assert "Emails sent: 1" in digest.text
            assert "Reply rate" not in digest.text  # analytics section is behind its flag
            assert lifecycle.weekly_digest(db) == 0  # once per week
            assert db.scalar(select(LifecycleEmail).where(LifecycleEmail.key.like("digest:%")))
    finally:
        db.close()
