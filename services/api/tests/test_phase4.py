from tests.conftest import auth_headers, get_client


def test_scoring_rules_and_recalculate():
    client = get_client()
    headers = auth_headers(client)

    rules = client.get("/scoring/rules", headers=headers)
    assert rules.status_code == 200
    assert len(rules.json()) >= 8
    assert any(r["key"] == "target_role_match" for r in rules.json())

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Scoring Niche",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": ["agency"],
            "company_size_min": 50,
            "company_size_max": 5000,
        },
    ).json()["id"]

    lead_id = client.post(
        "/leads",
        headers=headers,
        json={
            "niche_id": niche_id,
            "full_name": "Sam Taylor",
            "job_title": "Quality Manager",
            "source_url": "https://example.com/source",
            "compliance_source_note": "Public directory listing",
            "qualification_notes": "Governance and operational evidence focus",
        },
    ).json()["id"]

    recalc = client.post(
        "/scoring/recalculate",
        headers=headers,
        json={"niche_id": niche_id},
    )
    assert recalc.status_code == 200
    body = recalc.json()
    assert body["updated"] == 1
    assert body["results"][0]["lead_id"] == lead_id
    assert body["results"][0]["total"] >= 55

    lead = client.get(f"/leads/{lead_id}", headers=headers).json()
    assert lead["score"] >= 55
    assert lead["status"] in {"qualified", "enriched", "new", "ready_for_outreach"}


def test_search_generate_run_and_save():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Search Niche",
            "country": "UK",
            "industry": "Healthcare",
            "target_roles": ["Head of People", "Technical Manager"],
            "keywords": ["NHS"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    generated = client.post(
        "/searches/generate-queries",
        headers=headers,
        json={"niche_id": niche_id},
    )
    assert generated.status_code == 200
    queries = generated.json()["queries"]
    assert len(queries) == 2
    assert all("site:linkedin.com/in" in q for q in queries)

    run = client.post(
        "/searches/run",
        headers=headers,
        json={"niche_id": niche_id, "query": queries[0], "limit": 5},
    )
    assert run.status_code == 201
    search_id = run.json()["id"]
    assert run.json()["result_count"] == 5
    assert run.json()["status"] == "completed"
    assert all("linkedin.com/in/" in r["url"] for r in run.json()["results"])

    detail = client.get(f"/searches/{search_id}", headers=headers)
    assert detail.status_code == 200

    first_url = run.json()["results"][0]["url"]
    saved = client.post(
        f"/searches/{search_id}/save-results",
        headers=headers,
        json={"selected_urls": [first_url]},
    )
    assert saved.status_code == 200
    assert saved.json()["created"] == 1

    leads = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()
    assert leads["total"] == 1
    assert leads["items"][0]["linkedin_url"] == first_url
    assert leads["items"][0]["source_url"] == first_url
    assert leads["items"][0]["compliance_source_note"]
