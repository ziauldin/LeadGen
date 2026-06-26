from tests.conftest import auth_headers, get_client

from tests.test_phase7 import WELLPREDICT_STEP, _create_lead_with_email


def test_reply_sync_after_send():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Reply test campaign",
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

    sync = client.post("/replies/sync", headers=headers)
    assert sync.status_code == 200
    assert sync.json()["synced"] == 1

    replies = client.get("/replies", headers=headers).json()
    assert replies["total"] == 1
    assert replies["items"][0]["classification"] == "positive"
    assert replies["items"][0]["lead_id"] == lead_id

    lead = client.get(f"/leads/{lead_id}", headers=headers).json()
    assert lead["status"] == "replied"


def test_patch_reply_mark_meeting_booked():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Meeting test",
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
        json={"mark_meeting_booked": True},
    )
    assert updated.status_code == 200

    lead = client.get(f"/leads/{lead_id}", headers=headers).json()
    assert lead["status"] == "meeting_booked"


def test_dashboard_summary():
    client = get_client()
    headers = auth_headers(client)
    _create_lead_with_email(client, headers)

    summary = client.get("/dashboard/summary", headers=headers)
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_leads"] >= 1


def test_classify_reply_body():
    from app.services.replies.classification import classify_reply_body

    assert classify_reply_body("Happy to chat next week") == "positive"
    assert classify_reply_body("Please unsubscribe me") == "unsubscribe"
    assert classify_reply_body("Random text") == "unknown"
