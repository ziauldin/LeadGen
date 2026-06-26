from tests.conftest import auth_headers, get_client

WELLPREDICT_STEP = {
    "step_number": 1,
    "delay_days": 0,
    "subject_template": "Quick question about {{company}}",
    "body_template": """Hi {{first_name}},

I came across {{company}} while looking at organisations where {{pain_point}} appear especially important.

Would it be unreasonable to ask whether this is something worth a brief conversation?

Regards,
{{sender_name}}

If this is not relevant, reply "not relevant" and I will not contact you again.
To opt out: {{unsubscribe_link}}""",
}


def _create_lead_with_email(client, headers):
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Campaign Niche",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    client.post(
        "/settings",
        headers=headers,
        json={"sender_name": "Sam Founder", "sender_company": "WellPredict"},
    )

    client.post(
        "/leads/import-csv",
        headers=headers,
        files={
            "file": (
                "leads.csv",
                "full_name,job_title,company,website,linkedin_url,email,source_url,"
                "compliance_source_note,niche\n"
                "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,"
                "alex@example-foods.co.uk,https://example.com/listing,"
                "Found via public listing,Campaign Niche\n",
                "text/csv",
            ),
        },
    )

    lead_id = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()["items"][0]["id"]
    return niche_id, lead_id


def test_campaign_flow_add_approve_and_send():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "WellPredict outreach",
            "daily_send_limit": 20,
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "steps": [WELLPREDICT_STEP],
        },
    )
    assert campaign.status_code == 201
    campaign_id = campaign.json()["id"]

    added = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    )
    assert added.status_code == 200
    assert added.json()["created"] == 1
    message_id = added.json()["message_ids"][0]

    approved = client.post(
        "/emails/approve",
        headers=headers,
        json={"email_message_id": message_id},
    )
    assert approved.status_code == 200
    assert approved.json()["message"]["status"] == "approved"

    started = client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["campaign"]["status"] == "active"

    processed = client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    assert processed.status_code == 200
    assert processed.json()["sent"] == 1

    lead = client.get(f"/leads/{lead_id}", headers=headers).json()
    assert lead["status"] == "contacted"


def test_send_blocked_when_campaign_paused():
    client = get_client()
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Paused campaign",
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

    processed = client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    assert processed.status_code == 200
    assert processed.json()["sent"] == 0
