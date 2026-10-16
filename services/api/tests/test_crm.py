from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.crm import Deal
from app.models.notification import Notification
from app.services.crm.service import due_reminders
from app.services.email_generation.templates import VARIABLES
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import approved_message


@pytest.fixture(autouse=True)
def crm_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_crm", True)


def _lead_id(client, headers):
    return client.get("/leads", headers=headers).json()["items"][0]["id"]


def test_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "feature_crm", False)
    client = get_client()
    headers = auth_headers(client)
    assert client.get("/deals/board", headers=headers).status_code == 404


def test_board_and_deal_lifecycle():
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    board = client.get("/deals/board", headers=headers).json()
    names = [s["name"] for s in board["stages"]]
    assert names == ["Interested", "Meeting booked", "Proposal", "Negotiation", "Won", "Lost"]
    stage_ids = {s["name"]: s["id"] for s in board["stages"]}

    lead_id = _lead_id(client, headers)
    created = client.post(
        "/deals",
        headers=headers,
        json={"lead_id": lead_id, "value_cents": 500000, "currency": "gbp"},
    )
    assert created.status_code == 201, created.text
    deal = created.json()
    assert deal["title"] == "Person 0" and deal["currency"] == "GBP"
    assert deal["stage_id"] == stage_ids["Interested"]
    assert deal["owner_name"] == "Test User"

    moved = client.patch(
        f"/deals/{deal['id']}", headers=headers, json={"stage_id": stage_ids["Proposal"]}
    ).json()
    assert moved["stage_id"] == stage_ids["Proposal"]
    board = client.get("/deals/board", headers=headers).json()
    assert board["weighted_pipeline_cents"] == 300000  # 60% of 5,000.00
    assert next(s for s in board["stages"] if s["name"] == "Proposal")["count"] == 1

    won = client.patch(
        f"/deals/{deal['id']}", headers=headers, json={"stage_id": stage_ids["Won"]}
    ).json()
    assert won["closed_at"] is not None
    assert (
        client.patch(f"/deals/{deal['id']}", headers=headers, json={"owner_id": 999999}).status_code
        == 400
    )
    assert (
        client.patch(f"/deals/{deal['id']}", headers=headers, json={"stage_id": 999999}).status_code
        == 400
    )

    other = auth_headers(client, "other@example.com")
    assert (
        client.patch(f"/deals/{deal['id']}", headers=other, json={"title": "Mine"}).status_code
        == 404
    )
    assert client.delete(f"/deals/{deal['id']}", headers=headers).status_code == 204


def test_interested_replies_open_one_deal():
    # The simulator's first canned reply is an interested one.
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    db = TestingSessionLocal()
    try:
        deals = db.scalars(select(Deal)).all()
        assert len(deals) == 1
        assert deals[0].source == "reply"
        assert deals[0].title.startswith("Person 0")
    finally:
        db.close()


def test_auto_deals_can_be_turned_off():
    # The simulator's first canned reply is an interested one.
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    assert (
        client.patch("/settings", headers=headers, json={"auto_create_deals": False}).json()[
            "auto_create_deals"
        ]
        is False
    )
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    db = TestingSessionLocal()
    try:
        assert db.scalars(select(Deal)).all() == []
    finally:
        db.close()


def test_tasks_and_reminders():
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    lead_id = _lead_id(client, headers)
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    overdue = client.post(
        "/tasks", headers=headers, json={"title": "Call Alex", "due_at": past, "lead_id": lead_id}
    )
    assert overdue.status_code == 201, overdue.text
    assert overdue.json()["assignee_name"] == "Test User"
    client.post("/tasks", headers=headers, json={"title": "Send proposal", "due_at": future})
    assert (
        client.post(
            "/tasks", headers=headers, json={"title": "x", "assignee_id": 999999}
        ).status_code
        == 400
    )

    assert [
        t["title"] for t in client.get("/tasks", headers=headers, params={"due": "overdue"}).json()
    ] == ["Call Alex"]
    assert [
        t["title"] for t in client.get("/tasks", headers=headers, params={"due": "upcoming"}).json()
    ] == ["Send proposal"]
    assert len(client.get("/tasks", headers=headers, params={"lead_id": lead_id}).json()) == 1

    db = TestingSessionLocal()
    try:
        assert due_reminders(db) == 1
        assert due_reminders(db) == 0  # once per task
        assert (
            db.scalar(select(Notification).where(Notification.kind == "task_due")).title
            == "Task due: Call Alex"
        )
    finally:
        db.close()

    done = client.patch(
        f"/tasks/{overdue.json()['id']}", headers=headers, json={"done": True}
    ).json()
    assert done["done_at"] is not None
    assert client.get("/tasks", headers=headers, params={"due": "overdue"}).json() == []


def test_notes_and_timeline():
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    lead_id = _lead_id(client, headers)

    note = client.post(
        f"/leads/{lead_id}/notes", headers=headers, json={"body": "Prefers calls after 2pm"}
    )
    assert note.status_code == 201
    assert (
        client.get(f"/leads/{lead_id}/notes", headers=headers).json()[0]["author_name"]
        == "Test User"
    )
    client.post("/tasks", headers=headers, json={"title": "Follow up", "lead_id": lead_id})
    client.post("/deals", headers=headers, json={"lead_id": lead_id})

    kinds = [
        event["kind"] for event in client.get(f"/leads/{lead_id}/timeline", headers=headers).json()
    ]
    for expected in ("email", "reply", "note", "task", "activity"):
        assert expected in kinds
    assert client.delete(f"/notes/{note.json()['id']}", headers=headers).status_code == 204


def test_meeting_link_variable():
    assert "meeting_link" in VARIABLES
    client = get_client()
    headers = auth_headers(client)
    assert (
        client.patch(
            "/settings", headers=headers, json={"meeting_link": "http://insecure.example"}
        ).status_code
        == 422
    )
    saved = client.patch(
        "/settings", headers=headers, json={"meeting_link": "https://cal.com/sam/intro"}
    ).json()
    assert saved["meeting_link"] == "https://cal.com/sam/intro"
