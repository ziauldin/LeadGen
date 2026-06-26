import hashlib
import re

from app.services.search.base import SearchResult


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "profile"


def _extract_terms(query: str) -> list[str]:
    return re.findall(r'"([^"]+)"', query)


class MockSearchProvider:
    provider_name = "mock"

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        terms = _extract_terms(query)
        role = terms[0] if len(terms) > 0 else "Professional"
        keyword = terms[1] if len(terms) > 1 else "Business"
        country = terms[2] if len(terms) > 2 else "UK"

        results: list[SearchResult] = []
        for index in range(min(limit, 8)):
            name_seed = f"{role}-{keyword}-{country}-{index}"
            slug = _slugify(name_seed)
            digest = hashlib.sha1(name_seed.encode()).hexdigest()[:8]
            url = f"https://www.linkedin.com/in/{slug}-{digest}"
            title = f"{role} at {keyword} — {country}"
            snippet = (
                f"Mock search result for {role} in {keyword} ({country}). "
                "URL stored from approved search provider — profile not crawled."
            )
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider=self.provider_name,
                ),
            )
        return results
