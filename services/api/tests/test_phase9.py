from tests.conftest import auth_headers, get_client

from tests.test_phase7 import WELLPREDICT_STEP, _create_lead_with_email


def test_reply_notes_and_export():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Notes test",
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "steps": [WELLPREDICT_STEP],
        },
    ).json()["id"]

    message_id = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()["message_ids"][0]

    client.post("/emails/approve", headers=headers, json={"email_message_id": message_id})
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)

    reply_id = client.get("/replies", headers=headers).json()["items"][0]["id"]
    updated = client.patch(
        f"/replies/{reply_id}",
        headers=headers,
        json={"notes": "Booked discovery call for Tuesday"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Booked discovery call for Tuesday"

    export = client.get("/replies/export-csv", headers=headers)
    assert export.status_code == 200
    assert "Booked discovery call" in export.text


def test_dashboard_includes_status_counts():
    client = get_client()
    headers = auth_headers(client)
    _create_lead_with_email(client, headers)

    summary = client.get("/dashboard/summary", headers=headers).json()
    assert "lead_status_counts" in summary
    assert isinstance(summary["lead_status_counts"], dict)


def test_unsubscribe_writes_audit_log():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Audit test",
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "steps": [WELLPREDICT_STEP],
        },
    ).json()["id"]

    message_id = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()["message_ids"][0]

    client.post("/emails/approve", headers=headers, json={"email_message_id": message_id})
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)

    from sqlalchemy import select

    from tests.conftest import TestingSessionLocal
    from app.models.audit_log import AuditLog
    from app.models.email_message import EmailMessage

    db = TestingSessionLocal()
    try:
        message = db.scalar(select(EmailMessage).where(EmailMessage.id == message_id))
        assert message and message.unsubscribe_token
        client.get(f"/unsubscribe/{message.unsubscribe_token}")
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "unsubscribe",
                AuditLog.entity_id == message_id,
            ),
        )
        assert audit is not None
    finally:
        db.close()
