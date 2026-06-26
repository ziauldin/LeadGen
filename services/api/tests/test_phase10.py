from tests.conftest import auth_headers, get_client

from tests.test_phase7 import _create_lead_with_email


def test_lead_outreach_readiness_endpoint():
    client = get_client()
    headers = auth_headers(client)
    _, lead_id = _create_lead_with_email(client, headers)

    readiness = client.get(f"/leads/{lead_id}/outreach-readiness", headers=headers)
    assert readiness.status_code == 200
    data = readiness.json()
    assert data["ready"] is True
    assert data["issues"] == []
