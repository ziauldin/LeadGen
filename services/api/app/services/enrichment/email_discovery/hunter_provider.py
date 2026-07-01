import httpx
from .base import DiscoveredEmail


GENERIC_PREFIXES = {
    "info", "contact", "hello", "admin", "support", "sales",
    "enquiries", "reception", "office", "team"
}


def classify_email_type(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    if local in GENERIC_PREFIXES:
        return "generic"
    if "." in local or "_" in local:
        return "named"
    return "role_based"


class HunterEmailDiscoveryProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def discover_by_domain(self, domain: str) -> list[DiscoveredEmail]:
        if not domain:
            return []

        url = "https://api.hunter.io/v2/domain-search"

        with httpx.Client(timeout=20) as client:
            response = client.get(
                url,
                params={
                    "domain": domain,
                    "api_key": self.api_key,
                },
            )

        if response.status_code == 401:
            raise ValueError("Hunter API authentication failed")

        if response.status_code == 429:
            raise ValueError("Hunter API rate limit exceeded")

        response.raise_for_status()

        payload = response.json()
        data = payload.get("data") or {}
        emails = data.get("emails") or []

        results: list[DiscoveredEmail] = []
        seen: set[str] = set()

        for item in emails:
            email = (item.get("value") or "").strip().lower()
            if not email or email in seen:
                continue

            seen.add(email)

            # Hunter returns confidence as an integer out of 100
            confidence_raw = item.get("confidence")
            confidence = (float(confidence_raw) / 100.0) if confidence_raw is not None else None

            results.append(
                DiscoveredEmail(
                    email=email,
                    email_type=classify_email_type(email),
                    confidence=confidence,
                    source="hunter",
                    source_url=domain,
                    first_name=item.get("first_name"),
                    last_name=item.get("last_name"),
                    position=item.get("position"),
                    department=item.get("department"),
                )
            )

        return results
