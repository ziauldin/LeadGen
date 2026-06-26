from urllib.parse import urljoin, urlparse

from app.services.companies.helpers import extract_domain, normalize_website


def resolve_website(website: str | None) -> tuple[str | None, str | None]:
    normalized = normalize_website(website)
    if not normalized:
        return None, None
    domain = extract_domain(normalized)
    return normalized, domain


def is_same_domain(base_url: str, candidate_url: str) -> bool:
    base_domain = extract_domain(base_url)
    candidate_domain = extract_domain(candidate_url)
    return bool(base_domain and candidate_domain and base_domain == candidate_domain)


def make_absolute(base_url: str, href: str) -> str | None:
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return absolute
