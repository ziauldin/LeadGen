"""DNS checks for a sending domain: SPF, DKIM, DMARC and MX.

These are read-only lookups that explain what to fix; nothing here changes DNS.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import dns.exception
import dns.resolver

Lookup = Callable[[str, str], list[str]]

_HOSTNAME = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")

DKIM_SELECTORS: dict[str, tuple[str, ...]] = {
    "resend": ("resend",),
    "sendgrid": ("s1", "s2", "em"),
    "mailgun": ("k1", "mx", "smtp", "pic"),
}
COMMON_SELECTORS = ("default", "google", "selector1", "selector2", "k1", "s1", "dkim", "mail")


class LookupFailedError(Exception):
    pass


@dataclass
class Check:
    name: str
    status: str  # pass | warn | fail | unknown
    detail: str
    records: list[str] = field(default_factory=list)


def valid_domain(domain: str) -> bool:
    return bool(_HOSTNAME.match(domain.strip().lower().rstrip(".")))


def dns_lookup(name: str, rdtype: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5.0
    try:
        answer = resolver.resolve(name, rdtype)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.exception.DNSException as exc:
        raise LookupFailedError(str(exc)) from exc
    records = []
    for rdata in answer:
        if rdtype == "TXT":
            records.append(b"".join(rdata.strings).decode(errors="replace"))
        else:
            records.append(rdata.to_text())
    return records


def _safe(lookup: Lookup, name: str, rdtype: str) -> list[str] | None:
    try:
        return lookup(name, rdtype)
    except LookupFailedError:
        return None


def check_spf(domain: str, lookup: Lookup) -> Check:
    records = _safe(lookup, domain, "TXT")
    if records is None:
        return Check("SPF", "unknown", "DNS lookup timed out; try again")
    spf = [r for r in records if r.lower().startswith("v=spf1")]
    if not spf:
        return Check(
            "SPF",
            "fail",
            "No SPF record. Add the TXT record your email provider gives you, e.g. "
            '"v=spf1 include:<provider> ~all".',
        )
    if len(spf) > 1:
        return Check("SPF", "fail", "More than one SPF record; merge them into one.", spf)
    if "+all" in spf[0].lower():
        return Check("SPF", "fail", '"+all" lets anyone send as you; use "~all" or "-all".', spf)
    if "?all" in spf[0].lower():
        return Check("SPF", "warn", '"?all" is neutral; "~all" or "-all" is safer.', spf)
    return Check("SPF", "pass", "SPF record found.", spf)


def check_dmarc(domain: str, lookup: Lookup) -> Check:
    records = _safe(lookup, f"_dmarc.{domain}", "TXT")
    if records is None:
        return Check("DMARC", "unknown", "DNS lookup timed out; try again")
    dmarc = [r for r in records if r.lower().startswith("v=dmarc1")]
    if not dmarc:
        return Check(
            "DMARC",
            "fail",
            "No DMARC record. Gmail and Yahoo require one for bulk senders; start with "
            '"v=DMARC1; p=none; rua=mailto:dmarc@' + domain + '".',
        )
    policy = re.search(r"\bp=(\w+)", dmarc[0].lower())
    if policy and policy.group(1) in {"quarantine", "reject"}:
        return Check("DMARC", "pass", f"DMARC policy is {policy.group(1)}.", dmarc)
    return Check(
        "DMARC",
        "warn",
        "DMARC is set to p=none (monitoring only). Move to quarantine once reports look clean.",
        dmarc,
    )


def check_dkim(domain: str, provider: str | None, lookup: Lookup) -> Check:
    selectors = DKIM_SELECTORS.get(provider or "", ()) + COMMON_SELECTORS
    for selector in dict.fromkeys(selectors):
        name = f"{selector}._domainkey.{domain}"
        records = (_safe(lookup, name, "TXT") or []) + (_safe(lookup, name, "CNAME") or [])
        if any("p=" in r.lower() or r.endswith(".") or "dkim" in r.lower() for r in records):
            return Check("DKIM", "pass", f"DKIM key found for selector {selector!r}.", records)
    return Check(
        "DKIM",
        "warn",
        "No DKIM key found at the usual selectors. Add the DKIM records from your email "
        "provider's domain settings (they name the selector).",
    )


def check_mx(domain: str, lookup: Lookup, *, label: str = "MX", required: bool = False) -> Check:
    records = _safe(lookup, domain, "MX")
    if records is None:
        return Check(label, "unknown", "DNS lookup timed out; try again")
    if records:
        return Check(label, "pass", f"{domain} can receive email.", records)
    return Check(
        label,
        "fail" if required else "warn",
        f"{domain} has no MX record, so replies to it can't be delivered.",
    )


def run_checks(
    domain: str,
    *,
    provider: str | None = None,
    inbound_domain: str | None = None,
    lookup: Lookup = dns_lookup,
) -> dict:
    domain = domain.strip().lower().rstrip(".")
    checks = [
        check_spf(domain, lookup),
        check_dkim(domain, provider, lookup),
        check_dmarc(domain, lookup),
        check_mx(domain, lookup),
    ]
    if inbound_domain:
        checks.append(check_mx(inbound_domain, lookup, label="Inbound replies", required=True))
    statuses = {check.status for check in checks}
    overall = "fail" if "fail" in statuses else "warn" if statuses - {"pass"} else "pass"
    return {
        "domain": domain,
        "provider": provider,
        "overall": overall,
        "checks": [asdict(check) for check in checks],
    }
