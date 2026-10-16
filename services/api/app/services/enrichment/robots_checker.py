from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.core.http import FetchError, UnsafeURLError, safe_get

ROBOTS_MAX_BYTES = 512_000


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def fetch_robots_parser(base_url: str, client: httpx.Client) -> tuple[RobotFileParser, bool]:
    """Fetch and parse robots.txt once. Returns ``(parser, fetched)``.

    A missing or unreachable robots.txt means "allow all" (``fetched`` is False). Unsafe
    hosts are not swallowed: ``UnsafeURLError`` propagates so enrichment stops.
    """
    parser = RobotFileParser()
    robots_url = urljoin(_origin(base_url), "/robots.txt")
    fetched = False

    try:
        result = safe_get(
            client,
            robots_url,
            timeout=settings.enrichment_request_timeout,
            max_bytes=ROBOTS_MAX_BYTES,
        )
        if result.status_code == 200 and result.text:
            parser.parse(result.text.splitlines())
            fetched = True
        else:
            parser.allow_all = True  # type: ignore[attr-defined]  # stdlib attribute, untyped
    except UnsafeURLError:
        raise
    except FetchError:
        parser.allow_all = True  # type: ignore[attr-defined]  # stdlib attribute, untyped

    return parser, fetched


def can_fetch(parser: RobotFileParser, url: str, user_agent: str) -> bool:
    if getattr(parser, "allow_all", False):
        return True
    return parser.can_fetch(user_agent, url)
