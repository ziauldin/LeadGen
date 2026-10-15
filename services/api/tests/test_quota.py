from app.models.workspace import UsageCounter, Workspace
from tests.conftest import TestingSessionLocal, auth_headers, get_client

HEADER = "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"


def _set_overrides(client, headers, **overrides):
    workspace_id = client.get("/workspaces/current", headers=headers).json()["id"]
    db = TestingSessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        workspace.plan_overrides = overrides
        db.commit()
    finally:
        db.close()
    return workspace_id


def _niche(client, headers):
    return client.post(
        "/niches",
        headers=headers,
        json={"name": "N", "country": "UK", "industry": "Legal"},
    ).json()["id"]


def test_lead_quota_returns_402():
    client = get_client()
    headers = auth_headers(client)
    _set_overrides(client, headers, monthly_leads=1)
    niche_id = _niche(client, headers)
    first = client.post("/leads", headers=headers, json={"niche_id": niche_id, "full_name": "A"})
    assert first.status_code == 201
    second = client.post("/leads", headers=headers, json={"niche_id": niche_id, "full_name": "B"})
    assert second.status_code == 402
    body = second.json()
    assert body["metric"] == "monthly_leads"
    assert body["limit"] == 1
    assert body["used"] == 1


def test_csv_import_stops_at_lead_quota():
    client = get_client()
    headers = auth_headers(client)
    _set_overrides(client, headers, monthly_leads=2)
    _niche(client, headers)
    rows = "".join(f"P{i},CEO,Co {i},,,,https://s.example,n,N\n" for i in range(5))
    result = client.post(
        "/leads/import-csv",
        headers=headers,
        files={"file": ("l.csv", HEADER + rows, "text/csv")},
    ).json()
    assert result["created"] == 2
    assert any("plan" in error for error in result["errors"])


def test_campaign_limit():
    client = get_client()
    headers = auth_headers(client)
    _set_overrides(client, headers, max_campaigns=1)
    niche_id = _niche(client, headers)
    assert (
        client.post(
            "/campaigns", headers=headers, json={"niche_id": niche_id, "name": "A"}
        ).status_code
        == 201
    )
    second = client.post("/campaigns", headers=headers, json={"niche_id": niche_id, "name": "B"})
    assert second.status_code == 402


def test_usage_counters_are_recorded_and_reported():
    client = get_client()
    headers = auth_headers(client)
    workspace_id = client.get("/workspaces/current", headers=headers).json()["id"]
    niche_id = _niche(client, headers)
    for name in ("A", "B", "C"):
        client.post("/leads", headers=headers, json={"niche_id": niche_id, "full_name": name})

    db = TestingSessionLocal()
    try:
        counter = (
            db.query(UsageCounter)
            .filter_by(workspace_id=workspace_id, metric="monthly_leads")
            .one()
        )
        assert counter.count == 3
    finally:
        db.close()

    billing = client.get("/billing", headers=headers).json()
    assert billing["plan"] == "free"
    leads_usage = next(item for item in billing["usage"] if item["metric"] == "monthly_leads")
    assert leads_usage["used"] == 3


def test_checkout_not_available_yet():
    client = get_client()
    headers = auth_headers(client)
    response = client.post("/billing/checkout", headers=headers, json={"plan": "pro"})
    assert response.status_code == 501


def test_seat_limit_blocks_invitations():
    client = get_client()
    headers = auth_headers(client)
    _set_overrides(client, headers, seats=1)
    response = client.post(
        "/workspaces/current/invitations",
        headers=headers,
        json={"email": "new@example.com"},
    )
    assert response.status_code == 402
