import re
from dataclasses import dataclass

from app.models.enums import EmailType

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)

IGNORED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js")
GENERIC_LOCAL_PARTS = {
    "info",
    "contact",
    "hello",
    "support",
    "admin",
    "sales",
    "enquiries",
    "office",
    "mail",
    "team",
}
ROLE_LOCAL_PREFIXES = (
    "hr",
    "quality",
    "compliance",
    "governance",
    "people",
    "operations",
    "recruitment",
    "talent",
    "careers",
)


@dataclass
class ExtractedEmail:
    email: str
    email_type: EmailType
    is_role_based: bool
    is_personal: bool
    confidence: float
    source_url: str


def _clean_email(raw: str) -> str | None:
    email = raw.strip().strip(".,;:").lower()
    if any(ext in email for ext in IGNORED_EXTENSIONS):
        return None
    if "@" not in email:
        return None
    local, domain = email.split("@", 1)
    if not local or not domain or "." not in domain:
        return None
    if domain.endswith(".example") or domain.endswith(".test"):
        return None
    return email


def classify_email(email: str) -> tuple[EmailType, bool, bool, float]:
    local = email.split("@", 1)[0].lower()

    if local in GENERIC_LOCAL_PARTS:
        return EmailType.GENERIC, False, False, 0.5

    if any(local.startswith(prefix) or local == prefix for prefix in ROLE_LOCAL_PREFIXES):
        return EmailType.ROLE_BASED, True, False, 0.75

    if "." in local and len(local) > 3 and local not in GENERIC_LOCAL_PARTS:
        return EmailType.NAMED, False, True, 0.85

    return EmailType.GENERIC, False, False, 0.55


def extract_emails_from_html(html: str, source_url: str) -> list[ExtractedEmail]:
    found: dict[str, ExtractedEmail] = {}

    for match in EMAIL_PATTERN.findall(html):
        cleaned = _clean_email(match)
        if cleaned is None or cleaned in found:
            continue
        email_type, is_role_based, is_personal, confidence = classify_email(cleaned)
        found[cleaned] = ExtractedEmail(
            email=cleaned,
            email_type=email_type,
            is_role_based=is_role_based,
            is_personal=is_personal,
            confidence=confidence,
            source_url=source_url,
        )

    return list(found.values())
