"""Outbound HTTP for user-supplied URLs (company websites), safe against SSRF.

Every hop is checked: only http/https on ports 80/443, and the host must resolve to public
addresses only. Private, loopback, link-local, CGNAT, cloud-metadata, multicast and IPv6 ULA
ranges (including Railway's private network) are rejected. Redirects are followed manually so
each target is re-validated, and response bodies are size-capped.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
MAX_REDIRECTS = 3


class UnsafeURLError(ValueError):
    """The URL points at a host or port we refuse to contact."""


class FetchError(Exception):
    """The remote site could not be fetched (network error, bad status, too large)."""


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    content_type: str


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def resolve_public_addresses(host: str, port: int) -> list[str]:
    """Resolve ``host`` and raise if any address is not public."""
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public_ip(literal):
            raise UnsafeURLError("Address is not publicly routable")
        return [str(literal)]

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve {host}") from exc
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses:
        raise FetchError(f"Could not resolve {host}")
    for address in addresses:
        if not _is_public_ip(ipaddress.ip_address(address.split("%")[0])):
            raise UnsafeURLError("Host resolves to a private or reserved address")
    return addresses


def validate_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no host")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError("Only ports 80 and 443 are allowed")
    resolve_public_addresses(parsed.hostname, port)
    return parsed.hostname, port


def _peer_is_public(response: httpx.Response) -> bool:
    """Re-check the address we actually connected to (defends against DNS rebinding)."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        return True
    try:
        server_addr = stream.get_extra_info("server_addr")
    except Exception:
        return True
    if not server_addr:
        return True
    try:
        return _is_public_ip(ipaddress.ip_address(str(server_addr[0]).split("%")[0]))
    except ValueError:
        return True


def safe_get(
    client: httpx.Client,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    max_redirects: int = MAX_REDIRECTS,
) -> FetchResult:
    """GET ``url`` following up to ``max_redirects`` validated redirects."""
    current = url
    for _ in range(max_redirects + 1):
        validate_url(current)
        try:
            with client.stream("GET", current, timeout=timeout, follow_redirects=False) as response:
                if not _peer_is_public(response):
                    raise UnsafeURLError("Connected address is not publicly routable")
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("Redirect without a Location header")
                    current = urljoin(current, location)
                    continue
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchError("Response is larger than the allowed size")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                return FetchResult(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=raw.decode(encoding, errors="replace"),
                    content_type=response.headers.get("content-type", ""),
                )
        except httpx.HTTPError as exc:
            raise FetchError(f"Request failed: {exc.__class__.__name__}") from exc
    raise FetchError("Too many redirects")
