import os

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

from tests.conftest import auth_headers, get_client


def test_provider_settings_list_and_upsert_mock():
    client = get_client()
    headers = auth_headers(client)

    listing = client.get("/provider-settings", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 2

    created = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "search",
            "provider_name": "mock",
            "config": {},
        },
    )
    assert created.status_code == 200
    assert created.json()["provider_name"] == "mock"
    assert created.json()["masked_summary"]
    assert "api_key" not in str(created.json())


def test_provider_settings_encrypts_secrets():
    client = get_client()
    headers = auth_headers(client)

    response = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "search",
            "provider_name": "serpapi",
            "config": {"api_key": "super-secret-serpapi-key-1234"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert "1234" in body["masked_summary"]
    assert "super-secret" not in body["masked_summary"]
    assert "super-secret" not in str(body)


def test_provider_settings_activate_and_test_mock():
    client = get_client()
    headers = auth_headers(client)

    credential_id = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "email",
            "provider_name": "mock",
            "config": {},
        },
    ).json()["id"]

    activated = client.patch(f"/provider-settings/{credential_id}/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    tested = client.post(f"/provider-settings/{credential_id}/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["success"] is True


def test_google_cse_provider_requires_credentials():
    from app.services.search.external_providers import GoogleCseSearchProvider, ProviderConfigurationError

    provider = GoogleCseSearchProvider(api_key="", search_engine_id="")
    try:
        provider.search("quality manager UK", limit=5)
        raise AssertionError("expected ProviderConfigurationError")
    except ProviderConfigurationError as exc:
        assert "api_key" in str(exc)
