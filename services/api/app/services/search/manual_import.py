from app.services.search.base import SearchResult


class ManualImportProvider:
    provider_name = "manual"

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        raise NotImplementedError("Manual import uses CSV lead import instead of search API")

    def from_rows(self, rows: list[dict[str, str]], limit: int = 100) -> list[SearchResult]:
        results: list[SearchResult] = []
        for row in rows[:limit]:
            results.append(
                SearchResult(
                    title=row.get("title") or row.get("full_name") or "Imported lead",
                    url=row.get("url") or row.get("linkedin_url") or row.get("source_url", ""),
                    snippet=row.get("snippet") or "Manual import",
                    provider=self.provider_name,
                ),
            )
        return results
