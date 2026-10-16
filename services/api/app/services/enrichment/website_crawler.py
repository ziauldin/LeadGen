import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.http import FetchError, UnsafeURLError, safe_get
from app.services.enrichment.robots_checker import can_fetch, fetch_robots_parser
from app.services.enrichment.website_finder import is_same_domain, make_absolute

CONTACT_KEYWORDS = ("contact", "about", "team", "people", "support")
USER_AGENT = settings.enrichment_user_agent


@dataclass
class CrawledPage:
    url: str
    html: str


def _path_matches_contact(path: str) -> bool:
    lowered = path.lower()
    return any(keyword in lowered for keyword in CONTACT_KEYWORDS)


def _discover_internal_links(base_url: str, html: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    discovered: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        absolute = make_absolute(base_url, str(anchor["href"]))
        if not absolute or absolute in seen:
            continue
        if not is_same_domain(base_url, absolute):
            continue
        path = urlparse(absolute).path or "/"
        if _path_matches_contact(path):
            seen.add(absolute)
            discovered.append(absolute)
        if len(discovered) >= limit:
            break

    return discovered


def _fetch(client: httpx.Client, url: str) -> CrawledPage | None:
    result = safe_get(
        client,
        url,
        timeout=settings.enrichment_request_timeout,
        max_bytes=settings.enrichment_max_response_bytes,
    )
    if result.status_code >= 400:
        return None
    return CrawledPage(url=result.url, html=result.text)


def crawl_company_site(
    base_url: str,
    *,
    robots_parser: RobotFileParser | None = None,
    max_pages: int | None = None,
) -> tuple[list[CrawledPage], str | None]:
    """Fetch the homepage plus up to ``max_pages - 1`` contact/about pages on the same domain."""
    page_budget = max(1, max_pages if max_pages is not None else settings.enrichment_max_pages)
    pages: list[CrawledPage] = []
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(headers=headers) as client:
        try:
            parser = robots_parser or fetch_robots_parser(base_url, client)[0]
        except UnsafeURLError:
            return [], "Website address is not allowed (private or reserved host)"

        if not can_fetch(parser, base_url, USER_AGENT):
            return [], "robots.txt disallows fetching the company homepage"

        try:
            homepage = _fetch(client, base_url)
        except UnsafeURLError:
            return [], "Website address is not allowed (private or reserved host)"
        except FetchError as exc:
            return [], f"Failed to fetch homepage: {exc}"
        if homepage is None:
            return [], "Failed to fetch homepage: the site returned an error status"

        pages.append(homepage)

        for link in _discover_internal_links(homepage.url, homepage.html, limit=page_budget - 1):
            time.sleep(settings.enrichment_rate_limit_seconds)
            if not can_fetch(parser, link, USER_AGENT):
                continue
            try:
                page = _fetch(client, link)
            except (UnsafeURLError, FetchError):
                continue
            if page is not None:
                pages.append(page)

    return pages, None
