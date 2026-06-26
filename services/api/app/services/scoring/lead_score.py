from dataclasses import dataclass

from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.enums import EmailType, LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.services.scoring.rules import RULES_BY_KEY


@dataclass
class ScoreBreakdownItem:
    rule_key: str
    label: str
    points: int
    reason: str


@dataclass
class ScoreResult:
    total: float
    breakdown: list[ScoreBreakdownItem]
    suggested_status: LeadStatus


GENERIC_PREFIXES = ("info@", "contact@", "hello@", "support@", "admin@", "sales@")


def _text_blob(lead: Lead, company: Company | None, niche: Niche) -> str:
    parts = [
        lead.full_name or "",
        lead.job_title or "",
        lead.qualification_notes or "",
        niche.industry or "",
    ]
    if company:
        parts.extend([company.name or "", company.industry or "", company.website or ""])
    return " ".join(parts).lower()


def _has_target_role_match(lead: Lead, niche: Niche) -> tuple[bool, str]:
    if not lead.job_title:
        return False, "No job title on lead"
    job = lead.job_title.lower()
    for role in niche.target_roles or []:
        if role.lower() in job or job in role.lower():
            return True, f"Job title matches target role '{role}'"
    return False, "Job title does not match niche target roles"


def _has_keyword_match(text: str, keywords: list) -> tuple[bool, str | None]:
    for keyword in keywords or []:
        if keyword.lower() in text:
            return True, keyword
    return False, None


def _is_generic_email(contact: EmailContact) -> bool:
    if contact.email_type == EmailType.GENERIC:
        return True
    email = contact.email.lower()
    return any(email.startswith(prefix) for prefix in GENERIC_PREFIXES)


def _has_non_generic_email(contacts: list[EmailContact]) -> bool:
    active = [c for c in contacts if not c.opted_out]
    return any(not _is_generic_email(c) for c in active)


def _has_any_email(contacts: list[EmailContact]) -> bool:
    return any(not c.opted_out for c in contacts)


def _only_generic_emails(contacts: list[EmailContact]) -> bool:
    active = [c for c in contacts if not c.opted_out]
    return bool(active) and all(_is_generic_email(c) for c in active)


def _company_size_matches(company: Company | None, niche: Niche) -> tuple[bool, str]:
    if company is None or company.size_estimate is None:
        return False, "No company size estimate"
    size = company.size_estimate
    min_size = niche.company_size_min
    max_size = niche.company_size_max
    if min_size is not None and size < min_size:
        return False, f"Company size {size} below niche minimum {min_size}"
    if max_size is not None and size > max_size:
        return False, f"Company size {size} above niche maximum {max_size}"
    if min_size is None and max_size is None:
        return False, "Niche has no company size filters"
    return True, f"Company size {size} within niche range"


def _suggest_status(lead: Lead, total: float, contacts: list[EmailContact]) -> LeadStatus:
    if any(c.opted_out for c in contacts):
        return LeadStatus.OPTED_OUT

    if lead.status in {
        LeadStatus.CONTACTED,
        LeadStatus.REPLIED,
        LeadStatus.MEETING_BOOKED,
        LeadStatus.CLIENT,
        LeadStatus.DISQUALIFIED,
    }:
        return lead.status

    has_email = _has_any_email(contacts)
    ready = (
        total >= 80
        and has_email
        and bool(lead.source_url)
        and bool(lead.compliance_source_note)
    )
    if ready:
        return LeadStatus.READY_FOR_OUTREACH
    if total >= 60:
        return LeadStatus.QUALIFIED
    if lead.company_id is not None:
        return LeadStatus.ENRICHED
    return LeadStatus.NEW


def score_lead(lead: Lead, niche: Niche) -> ScoreResult:
    company = lead.company
    contacts = list(lead.email_contacts or [])
    breakdown: list[ScoreBreakdownItem] = []
    text = _text_blob(lead, company, niche)

    if any(c.opted_out for c in contacts):
        rule = RULES_BY_KEY["opted_out"]
        breakdown.append(
            ScoreBreakdownItem(
                rule_key=rule.key,
                label=rule.label,
                points=0,
                reason="Email contact marked as opted out",
            ),
        )
        return ScoreResult(total=0.0, breakdown=breakdown, suggested_status=LeadStatus.OPTED_OUT)

    matched, reason = _has_target_role_match(lead, niche)
    if matched:
        rule = RULES_BY_KEY["target_role_match"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, reason),
        )

    keyword_match, keyword = _has_keyword_match(text, niche.keywords)
    if keyword_match:
        rule = RULES_BY_KEY["niche_keyword_match"]
        breakdown.append(
            ScoreBreakdownItem(
                rule.key,
                rule.label,
                rule.points,
                f"Matched niche keyword '{keyword}'",
            ),
        )

    exclusion_match, exclusion = _has_keyword_match(text, niche.exclusion_keywords)
    if exclusion_match:
        rule = RULES_BY_KEY["exclusion_keyword"]
        breakdown.append(
            ScoreBreakdownItem(
                rule.key,
                rule.label,
                rule.points,
                f"Matched exclusion keyword '{exclusion}'",
            ),
        )

    if company and company.website:
        rule = RULES_BY_KEY["company_website_exists"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, "Company website present"),
        )
    elif company is not None:
        rule = RULES_BY_KEY["no_website"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, "Company has no website"),
        )

    if _has_non_generic_email(contacts):
        rule = RULES_BY_KEY["public_email_found"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, "Non-generic email found"),
        )
    elif _only_generic_emails(contacts):
        rule = RULES_BY_KEY["generic_email_only"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, "Only generic email found"),
        )

    size_match, size_reason = _company_size_matches(company, niche)
    if size_match:
        rule = RULES_BY_KEY["company_size_match"]
        breakdown.append(
            ScoreBreakdownItem(rule.key, rule.label, rule.points, size_reason),
        )

    total = float(sum(item.points for item in breakdown))
    suggested = _suggest_status(lead, total, contacts)
    return ScoreResult(total=total, breakdown=breakdown, suggested_status=suggested)


def apply_score_result(lead: Lead, result: ScoreResult) -> None:
    lead.score = result.total
    if lead.status not in {
        LeadStatus.CONTACTED,
        LeadStatus.REPLIED,
        LeadStatus.MEETING_BOOKED,
        LeadStatus.CLIENT,
        LeadStatus.DISQUALIFIED,
    }:
        lead.status = result.suggested_status
