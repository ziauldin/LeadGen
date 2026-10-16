"""Shared setup for sending-pipeline tests: one workspace with an approved campaign email."""

from sqlalchemy import select

from app.models.email_message import EmailMessage
from tests.conftest import TestingSessionLocal, auth_headers

CSV_HEADER = "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"
STEP = {
    "step_number": 1,
    "delay_days": 0,
    "subject_template": "Quick question about {{company}}",
    "body_template": "Hi {{first_name}},\n\nWorth a chat?\n\n{{sender_name}}\n\n"
    'If this is not relevant, reply "not relevant". Opt out: {{unsubscribe_link}}',
}
ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]


def approved_message(client, *, emails=("alex@example-foods.co.uk",), campaign_overrides=None):
    """Return (headers, campaign_id, [message_ids]) with approved emails in an active campaign."""
    headers = auth_headers(client)
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={"name": "Send Niche", "country": "UK", "industry": "Food", "target_roles": ["QM"]},
    ).json()["id"]
    client.patch(
        "/settings",
        headers=headers,
        json={
            "sender_name": "Sam",
            "sender_company": "Acme Ltd",
            "business_address": "1 High St, London",
        },
    )
    rows = "".join(
        f"Person {i},Quality Manager,Company {i},https://company-{i}.co.uk,,{email},"
        f"https://example.com/listing,Public listing,Send Niche\n"
        for i, email in enumerate(emails)
    )
    client.post(
        "/leads/import-csv",
        headers=headers,
        files={"file": ("l.csv", CSV_HEADER + rows, "text/csv")},
    )
    lead_ids = [lead["id"] for lead in client.get("/leads", headers=headers).json()["items"]]
    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Send campaign",
            "daily_send_limit": 50,
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "sending_days": ALL_DAYS,
            "steps": [STEP],
            **(campaign_overrides or {}),
        },
    ).json()["id"]
    message_ids = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": lead_ids},
    ).json()["message_ids"]
    for message_id in message_ids:
        response = client.post(
            "/emails/approve",
            headers=headers,
            json={"email_message_id": message_id},
        )
        assert response.status_code == 200, response.text
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    return headers, campaign_id, message_ids


def load_message(message_id: int) -> EmailMessage:
    db = TestingSessionLocal()
    try:
        message = db.scalar(select(EmailMessage).where(EmailMessage.id == message_id))
        assert message is not None
        db.expunge(message)
        return message
    finally:
        db.close()
