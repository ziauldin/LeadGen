from dataclasses import dataclass
from urllib.parse import urljoin

from app.models.company import Company
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.models.user_settings import UserSettings


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
    if niche.industry:
        return (
            f"governance, operational pressure and evidence around team risk in {niche.industry.lower()}"
        )
    return "governance, operational pressure and evidence around team risk"


def build_context(
    lead: Lead,
    niche: Niche,
    user: User,
    settings: UserSettings | None,
    api_base_url: str,
    unsubscribe_token: str | None = None,
) -> PersonalisationContext:
    company_name = lead.company.name if lead.company else "your organisation"
    token = unsubscribe_token or "preview-token"
    unsubscribe_link = urljoin(api_base_url.rstrip("/") + "/", f"unsubscribe/{token}")

    return PersonalisationContext(
        first_name=derive_first_name(lead.full_name),
        company=company_name,
        role=lead.job_title or (niche.target_roles[0] if niche.target_roles else "your role"),
        industry=niche.industry,
        pain_point=default_pain_point(niche),
        sender_name=(settings.sender_name if settings and settings.sender_name else user.name),
        sender_company=(settings.sender_company if settings and settings.sender_company else "WellPredict"),
        unsubscribe_link=unsubscribe_link,
    )


def render_template(text: str, context: PersonalisationContext) -> str:
    rendered = text
    for key, value in context.__dict__.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
