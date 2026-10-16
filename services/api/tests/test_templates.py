from tests.conftest import auth_headers, get_client
from tests.test_phase6 import _create_lead_with_email

BODY = "Hello {{first_name}} at {{company}}.\n\nOpt out: {{unsubscribe_link}}"


def test_system_templates_are_listed_and_read_only():
    client = get_client()
    headers = auth_headers(client)
    templates = client.get("/templates", headers=headers).json()
    ids = [t["id"] for t in templates]
    assert "system:intro" in ids and "system:follow-up" in ids
    assert all(t["is_system"] for t in templates)
    assert all("wellpredict" not in t["body"].lower() for t in templates)

    legacy = client.get("/templates/wellpredict", headers=headers)
    assert legacy.status_code == 200
    assert legacy.json()["id"] == "system:intro"

    assert (
        client.patch("/templates/system:intro", headers=headers, json={"name": "x"}).status_code
        == 404
    )
    variables = client.get("/templates/variables", headers=headers).json()
    assert "first_name" in variables["variables"]
    assert variables["required"] == ["unsubscribe_link"]


def test_create_update_archive_and_use_a_template():
    client = get_client()
    headers = auth_headers(client)
    _, lead_id = _create_lead_with_email(client, headers)

    created = client.post(
        "/templates",
        headers=headers,
        json={"name": "Short intro", "subject": "Hi {{first_name}}", "body": BODY},
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]
    assert created.json()["is_system"] is False

    preview = client.post(
        "/emails/preview",
        headers=headers,
        json={"lead_id": lead_id, "template_id": template_id},
    ).json()
    assert preview["subject"] == "Hi Alex"
    assert preview["body"].startswith("Hello Alex at Example Foods.")
    assert preview["can_send"] is True

    updated = client.patch(
        f"/templates/{template_id}",
        headers=headers,
        json={"subject": "Quick note for {{company}}"},
    )
    assert updated.json()["subject"] == "Quick note for {{company}}"

    assert client.delete(f"/templates/{template_id}", headers=headers).status_code == 204
    listed = [t["id"] for t in client.get("/templates", headers=headers).json()]
    assert template_id not in listed
    with_archived = client.get("/templates?include_archived=true", headers=headers).json()
    assert any(t["id"] == template_id and t["is_archived"] for t in with_archived)


def test_template_validation():
    client = get_client()
    headers = auth_headers(client)
    unknown = client.post(
        "/templates",
        headers=headers,
        json={"name": "Bad", "subject": "Hi {{nickname}}", "body": BODY},
    )
    assert unknown.status_code == 400
    assert "nickname" in unknown.json()["detail"]

    no_opt_out = client.post(
        "/templates",
        headers=headers,
        json={"name": "Bad", "subject": "Hi", "body": "Hello {{first_name}}"},
    )
    assert no_opt_out.status_code == 400
    assert "unsubscribe_link" in no_opt_out.json()["detail"]


def test_templates_are_private_to_their_workspace():
    client = get_client()
    owner = auth_headers(client)
    template_id = client.post(
        "/templates",
        headers=owner,
        json={"name": "Mine", "subject": "Hi", "body": BODY},
    ).json()["id"]

    other = auth_headers(client, email="other@example.com")
    assert client.get(f"/templates/{template_id}", headers=other).status_code == 404
    assert (
        client.patch(f"/templates/{template_id}", headers=other, json={"name": "x"}).status_code
        == 404
    )
    assert client.delete(f"/templates/{template_id}", headers=other).status_code == 404
    assert template_id not in [t["id"] for t in client.get("/templates", headers=other).json()]


def test_campaign_step_can_use_a_saved_template():
    client = get_client()
    headers = auth_headers(client)
    niche_id, _lead_id = _create_lead_with_email(client, headers)
    template_id = client.post(
        "/templates",
        headers=headers,
        json={"name": "Step", "subject": "For {{company}}", "body": BODY},
    ).json()["id"]

    campaign = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Templated",
            "steps": [{"step_number": 1, "template_id": template_id}],
        },
    )
    assert campaign.status_code == 201, campaign.text
    step = campaign.json()["steps"][0]
    assert step["template_id"] == template_id
    assert step["subject_template"] == "For {{company}}"

    missing = client.post(
        "/campaigns",
        headers=headers,
        json={"niche_id": niche_id, "name": "Bad", "steps": [{"step_number": 1}]},
    )
    assert missing.status_code == 422

    unknown = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Bad",
            "steps": [{"step_number": 1, "template_id": "99999"}],
        },
    )
    assert unknown.status_code == 400
