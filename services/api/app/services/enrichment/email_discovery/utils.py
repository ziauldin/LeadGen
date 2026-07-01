from urllib.parse import urlparse
import tldextract


BLOCKED_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
}


def extract_company_domain(url_or_domain: str | None) -> str | None:
    if not url_or_domain:
        return None

    raw = url_or_domain.strip()

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = parsed.netloc.lower().replace("www.", "")

    if host in BLOCKED_DOMAINS or host.endswith(".linkedin.com"):
        return None

    extracted = tldextract.extract(host)
    if not extracted.domain or not extracted.suffix:
        return None

    return f"{extracted.domain}.{extracted.suffix}"
