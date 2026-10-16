"""Email address verification: ZeroBounce, NeverBounce, a mock, and a free DNS-only fallback.

Every verifier returns one of four statuses:
- valid: the mailbox exists and accepts mail
- risky: catch-all domains, role or disposable addresses, temporary problems
- invalid: bad syntax, no mail server, or the mailbox doesn't exist
- unknown: couldn't tell (e.g. the DNS-only check, or the provider timed out)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import dns.exception
import dns.resolver
import httpx

VALID, RISKY, INVALID, UNKNOWN = "valid", "risky", "invalid", "unknown"
STATUSES = (VALID, RISKY, INVALID, UNKNOWN)
_SYNTAX = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DISPOSABLE = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "10minutemail.com",
        "tempmail.com",
        "yopmail.com",
        "trashmail.com",
    }
)


@dataclass(frozen=True)
class VerificationResult:
    status: str
    detail: str
    provider: str
    billable: bool = True  # counts against the plan's verification credits


class Verifier(Protocol):
    name: str

    def verify(self, email: str) -> VerificationResult: ...


def http_client() -> httpx.Client:
    """Overridden in tests."""
    return httpx.Client(timeout=15.0)


def syntax_ok(email: str) -> bool:
    return bool(_SYNTAX.match(email)) and ".." not in email


class DnsVerifier:
    """Free fallback: syntax, disposable domains and whether the domain accepts mail at all."""

    name = "dns"

    def __init__(self, resolver: dns.resolver.Resolver | None = None) -> None:
        self.resolver = resolver

    def _has_mail_server(self, domain: str) -> bool | None:
        resolver = self.resolver or dns.resolver.Resolver()
        resolver.lifetime = 5.0
        for record in ("MX", "A"):
            try:
                if resolver.resolve(domain, record):
                    return True
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                continue
            except dns.exception.DNSException:
                return None  # couldn't tell
        return False

    def verify(self, email: str) -> VerificationResult:
        if not syntax_ok(email):
            return VerificationResult(
                INVALID, "Not a valid email address", self.name, billable=False
            )
        domain = email.rsplit("@", 1)[1].lower()
        if domain in DISPOSABLE:
            return VerificationResult(RISKY, "Disposable email domain", self.name, billable=False)
        has_server = self._has_mail_server(domain)
        if has_server is False:
            return VerificationResult(
                INVALID, "The domain doesn't accept email", self.name, billable=False
            )
        if has_server is None:
            return VerificationResult(UNKNOWN, "DNS lookup failed", self.name, billable=False)
        return VerificationResult(
            UNKNOWN, "Domain accepts email; mailbox not checked", self.name, billable=False
        )


class MockVerifier:
    """Deterministic results for development and tests."""

    name = "mock"

    def verify(self, email: str) -> VerificationResult:
        if not syntax_ok(email):
            return VerificationResult(INVALID, "Not a valid email address", self.name)
        local = email.split("@", 1)[0].lower()
        if local.startswith(("invalid", "bounce", "nobody")):
            return VerificationResult(INVALID, "Mailbox doesn't exist", self.name)
        if local.startswith(("risky", "catchall")):
            return VerificationResult(RISKY, "Catch-all domain", self.name)
        if local.startswith("unknown"):
            return VerificationResult(UNKNOWN, "Server didn't answer", self.name)
        return VerificationResult(VALID, "Mailbox exists", self.name)


class ZeroBounceVerifier:
    name = "zerobounce"
    URL = "https://api.zerobounce.net/v2/validate"
    MAP = {
        "valid": VALID,
        "invalid": INVALID,
        "spamtrap": INVALID,
        "do_not_mail": INVALID,
        "catch-all": RISKY,
        "abuse": RISKY,
        "unknown": UNKNOWN,
    }

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def verify(self, email: str) -> VerificationResult:
        try:
            with http_client() as client:
                response = client.get(
                    self.URL, params={"api_key": self.api_key, "email": email, "ip_address": ""}
                )
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return VerificationResult(
                UNKNOWN, "ZeroBounce didn't answer", self.name, billable=False
            )
        if response.status_code >= 400 or "error" in data:
            return VerificationResult(
                UNKNOWN, str(data.get("error", "ZeroBounce error"))[:200], self.name, billable=False
            )
        status = str(data.get("status", "unknown")).lower()
        sub = data.get("sub_status") or ""
        return VerificationResult(
            self.MAP.get(status, UNKNOWN), f"{status}{f' ({sub})' if sub else ''}", self.name
        )


class NeverBounceVerifier:
    name = "neverbounce"
    URL = "https://api.neverbounce.com/v4/single/check"
    MAP = {
        "valid": VALID,
        "invalid": INVALID,
        "disposable": INVALID,
        "catchall": RISKY,
        "unknown": UNKNOWN,
    }

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def verify(self, email: str) -> VerificationResult:
        try:
            with http_client() as client:
                response = client.get(self.URL, params={"key": self.api_key, "email": email})
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return VerificationResult(
                UNKNOWN, "NeverBounce didn't answer", self.name, billable=False
            )
        if response.status_code >= 400 or data.get("status") != "success":
            return VerificationResult(
                UNKNOWN,
                str(data.get("message", "NeverBounce error"))[:200],
                self.name,
                billable=False,
            )
        result = str(data.get("result", "unknown")).lower()
        return VerificationResult(self.MAP.get(result, UNKNOWN), result, self.name)
