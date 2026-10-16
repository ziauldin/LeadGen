"""Cross-workspace isolation: a member of workspace B must never read or change A's data."""

import re

import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.conftest import auth_headers, get_client

CSV = (
    "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"
    "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,"
    "alex@example-foods.co.uk,https://example.com/listing,Public listing,Iso Niche\n"
)
STEP = {
    "step_number": 1,
    "delay_days": 0,
    "subject_template": "Hello {{company}}",
    "body_template": "Hi {{first_name}}\n\nIf this is not relevant, reply not relevant.\n"
    "Opt out: {{unsubscribe_link}}",
}


def _build_workspace_a(client, headers) -> dict[str, int]:
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Iso Niche",
            "country": "UK",
            "industry": "Food",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
        },
    ).json()["id"]
    client.post("/leads/import-csv", headers=headers, files={"file": ("l.csv", CSV, "text/csv")})
    lead_id = client.get("/leads", headers=headers).json()["items"][0]["id"]
    company_id = client.get("/companies", headers=headers).json()["items"][0]["id"]
    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Iso campaign",
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "sending_days": [0, 1, 2, 3, 4, 5, 6],
            "steps": [STEP],
        },
    ).json()["id"]
    message_id = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()["message_ids"][0]
    client.post("/emails/approve", headers=headers, json={"email_message_id": message_id})
    enrollment_id = client.get(
        f"/campaigns/{campaign_id}/enrollments",
        headers=headers,
    ).json()["items"][0]["id"]
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    reply_id = client.get("/replies", headers=headers).json()["items"][0]["id"]
    search_id = client.post(
        "/searches/run",
        headers=headers,
        json={"niche_id": niche_id, "query": "quality managers", "limit": 2},
    ).json()["id"]
    credential_id = client.get("/provider-settings", headers=headers).json()["items"][0]["id"]
    suppression_id = client.post(
        "/suppressions",
        headers=headers,
        json={"email": "nope@example.com", "reason": "test"},
    ).json()["id"]
    return {
        "niche_id": niche_id,
        "lead_id": lead_id,
        "company_id": company_id,
        "campaign_id": campaign_id,
        "message_id": message_id,
        "enrollment_id": enrollment_id,
        "reply_id": reply_id,
        "search_id": search_id,
        "credential_id": credential_id,
        "suppression_id": suppression_id,
    }


# (method, path template, json body). Every route taking an object id must be listed here.
ATTACKS = [
    ("GET", "/niches/{niche_id}", None),
    ("PATCH", "/niches/{niche_id}", {"name": "pwned"}),
    ("DELETE", "/niches/{niche_id}", None),
    ("GET", "/leads/{lead_id}", None),
    ("PATCH", "/leads/{lead_id}", {"full_name": "pwned"}),
    ("DELETE", "/leads/{lead_id}", None),
    ("GET", "/leads/{lead_id}/outreach-readiness", None),
    ("GET", "/companies/{company_id}", None),
    ("PATCH", "/companies/{company_id}", {"name": "pwned"}),
    ("POST", "/companies/{company_id}/enrich?sync=true", None),
    ("GET", "/campaigns/{campaign_id}", None),
    ("PATCH", "/campaigns/{campaign_id}", {"name": "pwned"}),
    ("POST", "/campaigns/{campaign_id}/add-leads", {"lead_ids": ["{lead_id}"]}),
    ("POST", "/campaigns/{campaign_id}/start", None),
    ("POST", "/campaigns/{campaign_id}/pause", None),
    ("POST", "/campaigns/{campaign_id}/process-sends", None),
    ("GET", "/campaigns/{campaign_id}/enrollments", None),
    ("POST", "/campaigns/{campaign_id}/enrollments/{enrollment_id}/stop", None),
    ("PATCH", "/replies/{reply_id}", {"notes": "pwned"}),
    ("GET", "/replies/{reply_id}", None),
    ("POST", "/replies/{reply_id}/link", {"email_message_id": "{message_id}"}),
    ("GET", "/searches/{search_id}", None),
    ("POST", "/searches/{search_id}/save-results", {"selected_urls": []}),
    ("PATCH", "/provider-settings/{credential_id}/activate", None),
    ("POST", "/provider-settings/{credential_id}/test", None),
    ("DELETE", "/provider-settings/{credential_id}", None),
    ("PATCH", "/provider-settings/{credential_id}/warmup", {"enabled": True}),
    ("DELETE", "/suppressions/{suppression_id}", None),
    # Ids passed in request bodies.
    ("POST", "/emails/approve", {"email_message_id": "{message_id}"}),
    ("POST", "/emails/preview", {"lead_id": "{lead_id}"}),
    ("POST", "/emails/generate", {"lead_id": "{lead_id}"}),
    ("POST", "/leads", {"niche_id": "{niche_id}", "full_name": "x"}),
    ("POST", "/campaigns", {"niche_id": "{niche_id}", "name": "x"}),
    ("POST", "/searches/run", {"niche_id": "{niche_id}", "query": "x"}),
    ("POST", "/searches/generate-queries", {"niche_id": "{niche_id}"}),
    ("POST", "/scoring/recalculate", {"niche_id": "{niche_id}"}),
]

# Routes with ids that are not tenant objects (or are covered by dedicated tests).
EXEMPT_ID_ROUTES = {
    "/workspaces/{workspace_id}/switch",
    "/workspaces/current/members/{user_id}",
    "/workspaces/current/invitations/{invitation_id}",
    "/invitations/{token}",
    "/invitations/{token}/accept",
    "/unsubscribe/{token}",
}


def _fill(value, ids):
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        return ids[value[1:-1]]
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, ids) for v in value]
    return value


@pytest.fixture(scope="module")
def two_workspaces():
    client = get_client()
    headers_a = auth_headers(client, "alice@example.com")
    ids = _build_workspace_a(client, headers_a)
    headers_b = auth_headers(client, "mallory@example.com")
    return client, headers_a, headers_b, ids


@pytest.mark.parametrize(("method", "template", "body"), ATTACKS)
def test_other_workspace_cannot_touch_objects(two_workspaces, method, template, body):
    client, _headers_a, headers_b, ids = two_workspaces
    path = template.format(**ids)
    response = client.request(method, path, headers=headers_b, json=_fill(body, ids))
    assert response.status_code in {403, 404}, (method, path, response.status_code, response.text)


def test_lists_never_leak_across_workspaces(two_workspaces):
    client, headers_a, headers_b, ids = two_workspaces
    for path in (
        "/niches",
        "/leads",
        "/companies",
        "/campaigns",
        "/replies",
        "/suppressions",
    ):
        assert client.get(path, headers=headers_a).json()["total"] >= 1, path
        assert client.get(path, headers=headers_b).json()["total"] == 0, path
    provider_ids = {
        item["id"] for item in client.get("/provider-settings", headers=headers_b).json()["items"]
    }
    assert ids["credential_id"] not in provider_ids
    assert "Alex Morgan" not in client.get("/leads/export-csv", headers=headers_b).text
    assert client.get("/replies/export-csv", headers=headers_b).text.count("\n") == 1
    assert client.get("/dashboard/summary", headers=headers_b).json()["total_leads"] == 0


def test_workspace_header_for_foreign_workspace_is_rejected(two_workspaces):
    client, headers_a, headers_b, _ids = two_workspaces
    workspace_a = client.get("/workspaces/current", headers=headers_a).json()["id"]
    response = client.get("/leads", headers={**headers_b, "X-Workspace-Id": str(workspace_a)})
    assert response.status_code == 404


def test_objects_of_workspace_a_still_intact(two_workspaces):
    client, headers_a, _headers_b, ids = two_workspaces
    lead = client.get(f"/leads/{ids['lead_id']}", headers=headers_a).json()
    assert lead["full_name"] == "Alex Morgan"
    niche = client.get(f"/niches/{ids['niche_id']}", headers=headers_a).json()
    assert niche["name"] == "Iso Niche"


def test_every_id_route_is_covered():
    covered = {re.sub(r"\?.*$", "", template) for _, template, _ in ATTACKS}
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or "{" not in route.path:
            continue
        if route.path.startswith("/__test") or route.path in EXEMPT_ID_ROUTES:
            continue
        if route.path not in covered:
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, f"Add these id routes to the isolation matrix: {missing}"
