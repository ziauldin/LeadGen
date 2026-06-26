from datetime import UTC, datetime

import httpx
import smtplib

from app.models.enums import ProviderName
from app.models.provider_credential import ProviderCredential
from app.services.provider_credentials.service import _as_str, decrypt_provider_config
from app.services.search.external_providers import (
    BingSearchProvider,
    GoogleCseSearchProvider,
    SerpApiSearchProvider,
)
from app.services.search.mock_provider import MockSearchProvider


def test_search_provider(credential: ProviderCredential) -> tuple[bool, str]:
    provider_name = ProviderName(_as_str(credential.provider_name))
    if provider_name == ProviderName.MOCK:
        MockSearchProvider().search("test company", limit=1)
        return True, "Mock search provider is ready for local testing"

    config = decrypt_provider_config(credential)

    try:
        if provider_name == ProviderName.GOOGLE_CSE:
            GoogleCseSearchProvider(
                api_key=str(config["api_key"]),
                search_engine_id=str(config["search_engine_id"]),
            ).search("test company", limit=1)
        elif provider_name == ProviderName.BING:
            BingSearchProvider(
                api_key=str(config["api_key"]),
                endpoint=str(config.get("endpoint", "https://api.bing.microsoft.com/v7.0/search")),
            ).search("test company", limit=1)
        elif provider_name == ProviderName.SERPAPI:
            SerpApiSearchProvider(api_key=str(config["api_key"])).search("test company", limit=1)
        else:
            return False, f"Unsupported search provider: {_as_str(provider_name)}"
        return True, "Search connection successful"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def test_email_provider(credential: ProviderCredential) -> tuple[bool, str]:
    provider_name = ProviderName(_as_str(credential.provider_name))
    if provider_name == ProviderName.MOCK:
        return True, "Mock email provider is ready for simulated sends"

    config = decrypt_provider_config(credential)

    try:
        if provider_name == ProviderName.SMTP:
            host = str(config["host"])
            port = int(config.get("port", 587))
            username = str(config.get("username", ""))
            password = str(config.get("password", ""))
            use_tls = bool(config.get("use_tls", True))
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                if username:
                    server.login(username, password)
            return True, "SMTP connection and authentication successful"
        if provider_name == ProviderName.RESEND:
            response = httpx.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {config['api_key']}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return True, "Resend API key validated"
        if provider_name == ProviderName.SENDGRID:
            response = httpx.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {config['api_key']}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return True, "SendGrid API key validated"
        if provider_name == ProviderName.MAILGUN:
            domain = str(config["domain"])
            response = httpx.get(
                f"https://api.mailgun.net/v3/domains/{domain}",
                auth=("api", str(config["api_key"])),
                timeout=15.0,
            )
            response.raise_for_status()
            return True, "Mailgun API key and domain validated"
        return False, f"Unsupported email provider: {_as_str(provider_name)}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def test_provider_credential(credential: ProviderCredential) -> tuple[bool, str, datetime]:
    if _as_str(credential.provider_type) == "search":
        success, message = test_search_provider(credential)
    else:
        success, message = test_email_provider(credential)
    return success, message, datetime.now(UTC)
