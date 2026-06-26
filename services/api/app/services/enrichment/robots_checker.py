from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def fetch_robots_parser(base_url: str, client: httpx.Client) -> tuple[RobotFileParser, bool]:
    parser = RobotFileParser()
    origin = _origin(base_url)
    robots_url = urljoin(origin, "/robots.txt")
    fetched = False

    try:
        response = client.get(robots_url, timeout=settings.enrichment_request_timeout)
        if response.status_code == 200 and response.text:
            parser.parse(response.text.splitlines())
            fetched = True
        else:
            parser.allow_all = True
    except httpx.HTTPError:
        parser.allow_all = True

    return parser, fetched


def can_fetch(parser: RobotFileParser, url: str, user_agent: str) -> bool:
    if getattr(parser, "allow_all", False):
        return True
    return parser.can_fetch(user_agent, url)
