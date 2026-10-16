import socket
from unittest.mock import patch

import httpx
import pytest

from app.core.http import FetchError, UnsafeURLError, safe_get, validate_url
from tests.conftest import auth_headers, get_client


def _fake_resolve(mapping: dict[str, str]):
    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]

    return getaddrinfo


PUBLIC = {"example.com": "93.184.216.34"}


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[fd12:3456::1]/",
        "http://0.0.0.0/",
    ],
)
def test_private_and_metadata_addresses_are_blocked(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/",
        "file:///etc/passwd",
        "http://example.com:8080/",
        "http://user:pass@example.com/",
    ],
)
def test_bad_schemes_ports_and_credentials_are_blocked(url):
    with patch("socket.getaddrinfo", _fake_resolve(PUBLIC)), pytest.raises(UnsafeURLError):
        validate_url(url)


def test_hostname_resolving_to_private_ip_is_blocked():
    with (
        patch("socket.getaddrinfo", _fake_resolve({"internal.example": "10.1.2.3"})),
        pytest.raises(UnsafeURLError),
    ):
        validate_url("https://internal.example/")


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_redirect_to_private_address_is_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    with (
        patch("socket.getaddrinfo", _fake_resolve(PUBLIC)),
        _client(handler) as client,
        pytest.raises(UnsafeURLError),
    ):
        safe_get(client, "https://example.com/", timeout=5, max_bytes=1000)


def test_public_redirect_is_followed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "/contact"})
        return httpx.Response(200, text="hello contact page")

    with patch("socket.getaddrinfo", _fake_resolve(PUBLIC)), _client(handler) as client:
        result = safe_get(client, "https://example.com/", timeout=5, max_bytes=1000)
    assert result.status_code == 200
    assert result.url.endswith("/contact")
    assert "contact" in result.text


def test_response_size_is_capped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    with (
        patch("socket.getaddrinfo", _fake_resolve(PUBLIC)),
        _client(handler) as client,
        pytest.raises(FetchError),
    ):
        safe_get(client, "https://example.com/", timeout=5, max_bytes=1000)


def test_too_many_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/again"})

    with (
        patch("socket.getaddrinfo", _fake_resolve(PUBLIC)),
        _client(handler) as client,
        pytest.raises(FetchError),
    ):
        safe_get(client, "https://example.com/", timeout=5, max_bytes=1000)


def test_enrichment_reports_unsafe_website_without_leaking_details():
    client = get_client()
    headers = auth_headers(client)
    client.post(
        "/niches",
        headers=headers,
        json={
            "name": "N",
            "country": "UK",
            "industry": "Legal",
            "target_roles": [],
            "keywords": [],
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
                "A B,Partner,Metadata Ltd,http://169.254.169.254,,,https://x.example/s,note,N\n",
                "text/csv",
            ),
        },
    )
    company_id = client.get("/companies", headers=headers).json()["items"][0]["id"]
    response = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "not allowed" in response.json()["message"]
