from dataclasses import dataclass
from urllib.parse import urljoin

from app.models.lead import Lead
from app.models.niche import Niche
from app.models.workspace import WorkspaceSettings


@dataclass
class PersonalisationContext:
    first_name: str
    company: str
    role: str
    industry: str
    pain_point: str
    sender_name: str
    sender_company: str
    unsubscribe_link: str


def derive_first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else "there"


def default_pain_point(niche: Niche) -> str:
    """A neutral topic line built from the niche: its first keywords, else its industry."""
    keywords = [str(k).strip() for k in (niche.keywords or []) if str(k).strip()]
    if keywords:
        return " and ".join(keywords[:2]).lower()
    if niche.industry:
        return f"the priorities {niche.industry.lower()} teams are working on this year"
    return "the priorities teams like yours are working on this year"


def unsubscribe_url(api_base_url: str, token: str) -> str:
    return urljoin(api_base_url.rstrip("/") + "/", f"unsubscribe/{token}")


def build_context(
    lead: Lead,
    niche: Niche,
    settings: WorkspaceSettings | None,
    *,
    sender_fallback_name: str,
    api_base_url: str,
    unsubscribe_token: str | None = None,
) -> PersonalisationContext:
    company_name = lead.company.name if lead.company else "your organisation"
    sender_name = (settings.sender_name if settings and settings.sender_name else None) or (
        sender_fallback_name
    )
    sender_company = (
        settings.sender_company if settings and settings.sender_company else None
    ) or sender_name

    return PersonalisationContext(
        first_name=derive_first_name(lead.full_name),
        company=company_name,
        role=lead.job_title or (niche.target_roles[0] if niche.target_roles else "your role"),
        industry=niche.industry,
        pain_point=default_pain_point(niche),
        sender_name=sender_name,
        sender_company=sender_company,
        unsubscribe_link=unsubscribe_url(api_base_url, unsubscribe_token or "preview-token"),
    )


def render_template(text: str, context: PersonalisationContext) -> str:
    rendered = text
    for key, value in context.__dict__.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
