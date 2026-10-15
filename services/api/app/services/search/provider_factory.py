from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProviderName, ProviderType
from app.models.provider_credential import ProviderCredential
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


def find_search_credential(
    db: Session, workspace_id: int, provider_name: str
) -> ProviderCredential | None:
    """The workspace's configured search credential for one provider (active first)."""
    return db.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider_type == ProviderType.SEARCH,
            ProviderCredential.provider_name == ProviderName(provider_name),
        )
        .order_by(ProviderCredential.is_active.desc(), ProviderCredential.id.desc())
        .limit(1),
    )


def get_search_provider_for_workspace(
    db: Session, workspace_id: int, provider_name: str | None = None
):
    """The provider to search with: the requested one, else the workspace's active one."""
    if provider_name == ProviderName.MOCK.value:
        return MockSearchProvider()
    if provider_name:
        credential = find_search_credential(db, workspace_id, provider_name)
    else:
        credential = get_active_credential(db, workspace_id, ProviderType.SEARCH)
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


def get_active_search_provider_name(db: Session, workspace_id: int) -> str:
    credential = get_active_credential(db, workspace_id, ProviderType.SEARCH)
    if credential is None:
        return ProviderName.MOCK.value
    return _as_str(credential.provider_name)
