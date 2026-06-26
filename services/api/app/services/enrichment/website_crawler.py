import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
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
        absolute = make_absolute(base_url, anchor["href"])
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


def crawl_company_site(base_url: str) -> tuple[list[CrawledPage], str | None]:
    pages: list[CrawledPage] = []
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        parser, _ = fetch_robots_parser(base_url, client)
        if not can_fetch(parser, base_url, USER_AGENT):
            return [], "robots.txt disallows fetching the company homepage"

        try:
            homepage = client.get(base_url, timeout=settings.enrichment_request_timeout)
            homepage.raise_for_status()
        except httpx.HTTPError as exc:
            return [], f"Failed to fetch homepage: {exc}"

        pages.append(CrawledPage(url=str(homepage.url), html=homepage.text))

        extra_links = _discover_internal_links(str(homepage.url), homepage.text, limit=2)
        for link in extra_links:
            time.sleep(settings.enrichment_rate_limit_seconds)
            if not can_fetch(parser, link, USER_AGENT):
                continue
            try:
                response = client.get(link, timeout=settings.enrichment_request_timeout)
                response.raise_for_status()
                pages.append(CrawledPage(url=str(response.url), html=response.text))
            except httpx.HTTPError:
                continue

    return pages, None
