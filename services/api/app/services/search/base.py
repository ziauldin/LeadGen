from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchResult":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            provider=data.get("provider", ""),
        )
