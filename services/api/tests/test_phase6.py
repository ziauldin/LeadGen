from tests.conftest import auth_headers, get_client


def _create_lead_with_email(client, headers):
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Email Niche",
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
        json={
            "sender_name": "Sam Founder",
            "sender_company": "WellPredict",
            "business_address": "London, UK",
        },
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
                "Found via public company listing,Email Niche\n",
                "text/csv",
            ),
        },
    )

    lead_id = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()["items"][0]["id"]
    return niche_id, lead_id


def test_email_preview_generate_and_approve():
    client = get_client()
    headers = auth_headers(client)
    _, lead_id = _create_lead_with_email(client, headers)

    templates = client.get("/emails/templates", headers=headers)
    assert templates.status_code == 200
    assert any(t["id"] == "wellpredict" for t in templates.json())

    preview = client.post(
        "/emails/preview",
        headers=headers,
        json={"lead_id": lead_id, "template_id": "wellpredict"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["has_opt_out_line"] is True
    assert body["can_send"] is True
    assert "Example Foods" in body["subject"]
    assert "Alex" in body["body"]
    assert "WellPredict" in body["body"]

    generated = client.post(
        "/emails/generate",
        headers=headers,
        json={"lead_id": lead_id, "template_id": "wellpredict"},
    )
    assert generated.status_code == 201
    message = generated.json()["message"]
    assert message["status"] == "draft"
    assert message["unsubscribe_token"]

    approved = client.post(
        "/emails/approve",
        headers=headers,
        json={"email_message_id": message["id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["message"]["status"] == "approved"


def test_generate_blocked_without_compliance_note():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Blocked Email Niche",
            "country": "UK",
            "industry": "Healthcare",
            "target_roles": ["Head of People"],
            "keywords": ["NHS"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    lead_id = client.post(
        "/leads",
        headers=headers,
        json={
            "niche_id": niche_id,
            "full_name": "Jamie Lee",
            "job_title": "Head of People",
            "source_url": "https://example.com/source",
        },
    ).json()["id"]

    preview = client.post(
        "/emails/preview",
        headers=headers,
        json={"lead_id": lead_id},
    )
    assert preview.status_code == 200
    assert preview.json()["can_send"] is False
    assert any("compliance" in err.lower() for err in preview.json()["compliance_errors"])

    generate = client.post(
        "/emails/generate",
        headers=headers,
        json={"lead_id": lead_id},
    )
    assert generate.status_code == 400
