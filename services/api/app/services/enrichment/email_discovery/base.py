from dataclasses import dataclass
from typing import Protocol


@dataclass
class DiscoveredEmail:
    email: str
    email_type: str
    confidence: float | None
    source: str
    source_url: str | None
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    department: str | None = None


class EmailDiscoveryProvider(Protocol):
    def discover_by_domain(self, domain: str) -> list[DiscoveredEmail]:
        ...
