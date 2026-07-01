import pytest
import httpx
from unittest.mock import patch, MagicMock

from app.services.enrichment.email_discovery.hunter_provider import (
    HunterEmailDiscoveryProvider,
    classify_email_type,
)
from app.services.enrichment.email_discovery.base import DiscoveredEmail
from app.services.enrichment.email_discovery.utils import extract_company_domain


def test_classify_email_type():
    assert classify_email_type("info@domain.com") == "generic"
    assert classify_email_type("contact@domain.com") == "generic"
    assert classify_email_type("sales@domain.com") == "generic"
    assert classify_email_type("john.doe@domain.com") == "named"
    assert classify_email_type("jane_smith@domain.com") == "named"
    assert classify_email_type("ceo@domain.com") == "role_based"


def test_extract_company_domain():
    assert extract_company_domain("https://www.example.com/about") == "example.com"
    assert extract_company_domain("http://sub.domain.co.uk") == "domain.co.uk"
    assert extract_company_domain("example.com") == "example.com"
    assert extract_company_domain("https://linkedin.com/in/someuser") is None
    assert extract_company_domain("https://www.linkedin.com/company/some-corp") is None
    assert extract_company_domain("https://youtube.com/channel/123") is None
    assert extract_company_domain(None) is None


@patch("httpx.Client")
def test_hunter_provider_success(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "emails": [
                {
                    "value": "info@example.com",
                    "confidence": 95,
                    "first_name": None,
                    "last_name": None
                },
                {
                    "value": "john.doe@example.com",
                    "confidence": 88,
                    "first_name": "John",
                    "last_name": "Doe",
                    "position": "CEO"
                },
                {
                    "value": "info@example.com",  # Duplicate
                    "confidence": 95
                }
            ]
        }
    }
    mock_client.get.return_value = mock_response

    provider = HunterEmailDiscoveryProvider("fake_key")
    results = provider.discover_by_domain("example.com")

    assert len(results) == 2
    
    assert results[0].email == "info@example.com"
    assert results[0].email_type == "generic"
    assert results[0].confidence == 0.95
    assert results[0].source == "hunter"
    
    assert results[1].email == "john.doe@example.com"
    assert results[1].email_type == "named"
    assert results[1].confidence == 0.88
    assert results[1].first_name == "John"
    assert results[1].position == "CEO"


@patch("httpx.Client")
def test_hunter_provider_empty(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"emails": []}}
    mock_client.get.return_value = mock_response

    provider = HunterEmailDiscoveryProvider("fake_key")
    results = provider.discover_by_domain("example.com")
    assert len(results) == 0


@patch("httpx.Client")
def test_hunter_provider_401(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_client.get.return_value = mock_response

    provider = HunterEmailDiscoveryProvider("bad_key")
    with pytest.raises(ValueError, match="Hunter API authentication failed"):
        provider.discover_by_domain("example.com")


@patch("httpx.Client")
def test_hunter_provider_429(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_client.get.return_value = mock_response

    provider = HunterEmailDiscoveryProvider("fake_key")
    with pytest.raises(ValueError, match="Hunter API rate limit exceeded"):
        provider.discover_by_domain("example.com")
