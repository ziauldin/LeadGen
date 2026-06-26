from tests.conftest import auth_headers, get_client


def test_niches_crud():
    client = get_client()
    headers = auth_headers(client)

    create = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "UK Regulated Orgs",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": ["agency"],
            "company_size_min": 50,
            "company_size_max": 5000,
        },
    )
    assert create.status_code == 201
    niche_id = create.json()["id"]

    listing = client.get("/niches", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert len(listing.json()["items"]) == 1

    detail = client.get(f"/niches/{niche_id}", headers=headers)
    assert detail.status_code == 200

    updated = client.patch(
        f"/niches/{niche_id}",
        headers=headers,
        json={"name": "UK Regulated Organisations"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "UK Regulated Organisations"

    deleted = client.delete(f"/niches/{niche_id}", headers=headers)
    assert deleted.status_code == 204


def test_leads_crud_and_csv():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Test Niche",
            "country": "UK",
            "industry": "Healthcare",
            "target_roles": ["Head of People"],
            "keywords": ["NHS"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    company_resp = client.post(
        "/leads",
        headers=headers,
        json={
            "niche_id": niche_id,
            "full_name": "Jane Smith",
            "job_title": "Quality Manager",
            "source_url": "https://example.com/source",
            "compliance_source_note": "Found via public directory",
        },
    )
    assert company_resp.status_code == 201
    lead_id = company_resp.json()["id"]

    csv_content = (
        "full_name,job_title,company,website,linkedin_url,email,source_url,"
        "compliance_source_note,niche\n"
        "John Doe,Operations Director,Acme Foods,https://acme.example,,"
        "john@acme.example,https://example.com/john,Public listing,Test Niche\n"
    )
    import_resp = client.post(
        "/leads/import-csv",
        headers=headers,
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["created"] == 1

    export_resp = client.get("/leads/export-csv", headers=headers)
    assert export_resp.status_code == 200
    assert "John Doe" in export_resp.text

    patch_resp = client.patch(
        f"/leads/{lead_id}",
        headers=headers,
        json={"status": "qualified", "score": 75},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "qualified"

    list_resp = client.get("/leads?min_score=70", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


def test_suppressions_and_settings():
    client = get_client()
    headers = auth_headers(client)

    settings_resp = client.patch(
        "/settings",
        headers=headers,
        json={
            "sender_name": "Alex Founder",
            "sender_company": "WellPredict",
            "business_address": "London, UK",
        },
    )
    assert settings_resp.status_code == 200
    assert settings_resp.json()["sender_company"] == "WellPredict"

    suppression_resp = client.post(
        "/suppressions",
        headers=headers,
        json={"email": "blocked@example.com", "reason": "requested removal"},
    )
    assert suppression_resp.status_code == 201

    list_resp = client.get("/suppressions", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
