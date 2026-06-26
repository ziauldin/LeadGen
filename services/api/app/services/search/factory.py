from app.core.config import settings
from app.services.search.external_providers import (
    BingSearchProvider,
    GoogleCseSearchProvider,
    SerpApiSearchProvider,
)
from app.services.search.manual_import import ManualImportProvider
from app.services.search.mock_provider import MockSearchProvider


def get_search_provider():
    provider_key = settings.search_provider.lower()
    if provider_key == "mock":
        return MockSearchProvider()
    if provider_key == "manual":
        return ManualImportProvider()
    if provider_key == "google_cse":
        return GoogleCseSearchProvider()
    if provider_key == "bing":
        return BingSearchProvider()
    if provider_key == "serpapi":
        return SerpApiSearchProvider()
    raise NotImplementedError(
        f"Search provider '{settings.search_provider}' is not configured. Use 'mock' for local development.",
    )
