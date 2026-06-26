from urllib.parse import urlparse

import tldextract


def extract_domain(website: str | None) -> str | None:
    if not website or not website.strip():
        return None

    value = website.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    parsed = urlparse(value)
    host = parsed.netloc or parsed.path.split("/")[0]
    if not host:
        return None

    extracted = tldextract.extract(host)
    if not extracted.domain or not extracted.suffix:
        return host.lower().removeprefix("www.")

    return f"{extracted.domain}.{extracted.suffix}".lower()


def normalize_website(website: str | None) -> str | None:
    if not website or not website.strip():
        return None

    value = website.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value
