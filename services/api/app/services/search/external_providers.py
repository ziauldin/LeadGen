"""Approved search API providers (not HTML scraping)."""

import httpx

from app.services.search.base import SearchResult


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider is selected without required credentials."""


class GoogleCseSearchProvider:
    provider_name = "google_cse"

    def __init__(self, api_key: str, search_engine_id: str):
        self.api_key = api_key
        self.search_engine_id = search_engine_id

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.api_key or not self.search_engine_id:
            raise ProviderConfigurationError(
                "Google CSE requires api_key and search_engine_id",
            )

        response = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": min(limit, 10),
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("items", [])[:limit]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    provider=self.provider_name,
                ),
            )
        return results


class BingSearchProvider:
    provider_name = "bing"

    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://api.bing.microsoft.com/v7.0/search",
    ):
        self.api_key = api_key
        self.endpoint = endpoint

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.api_key:
            raise ProviderConfigurationError("Bing search requires api_key")

        response = httpx.get(
            self.endpoint,
            params={"q": query, "count": min(limit, 50)},
            headers={"Ocp-Apim-Subscription-Key": self.api_key},
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("webPages", {}).get("value", [])[:limit]:
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    provider=self.provider_name,
                ),
            )
        return results


class SerpApiSearchProvider:
    provider_name = "serpapi"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.api_key:
            raise ProviderConfigurationError("SerpAPI requires api_key")

        response = httpx.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "num": min(limit, 10),
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("organic_results", [])[:limit]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    provider=self.provider_name,
                ),
            )
        return results
