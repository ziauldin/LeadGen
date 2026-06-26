from sqlalchemy.orm import Session

from app.models.enums import ProviderName, ProviderType
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)
from app.services.search.external_providers import (
    BingSearchProvider,
    GoogleCseSearchProvider,
    SerpApiSearchProvider,
)
from app.services.search.mock_provider import MockSearchProvider


def get_search_provider_for_user(db: Session, user_id: int):
    credential = get_active_credential(db, user_id, ProviderType.SEARCH)
    if credential is None:
        return MockSearchProvider()

    provider_name_raw = credential.provider_name
    provider_name = ProviderName(_as_str(provider_name_raw))
    if provider_name == ProviderName.MOCK:
        return MockSearchProvider()

    config = decrypt_provider_config(credential)
    if provider_name == ProviderName.GOOGLE_CSE:
        return GoogleCseSearchProvider(
            api_key=str(config.get("api_key", "")),
            search_engine_id=str(config.get("search_engine_id", "")),
        )
    if provider_name == ProviderName.BING:
        return BingSearchProvider(
            api_key=str(config.get("api_key", "")),
            endpoint=str(config.get("endpoint", "https://api.bing.microsoft.com/v7.0/search")),
        )
    if provider_name == ProviderName.SERPAPI:
        return SerpApiSearchProvider(api_key=str(config.get("api_key", "")))

    return MockSearchProvider()


def get_active_search_provider_name(db: Session, user_id: int) -> str:
    credential = get_active_credential(db, user_id, ProviderType.SEARCH)
    if credential is None:
        return ProviderName.MOCK.value
    return _as_str(credential.provider_name)
