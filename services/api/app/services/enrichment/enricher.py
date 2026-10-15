"""Company enrichment: public website crawl (robots.txt respected) plus optional Hunter lookup."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.http import UnsafeURLError
from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.enums import EmailType, EnrichmentStatus, LeadStatus
from app.models.lead import Lead
from app.services.enrichment.email_extractor import extract_emails_from_html
from app.services.enrichment.robots_checker import fetch_robots_parser
from app.services.enrichment.website_crawler import CrawledPage, crawl_company_site
from app.services.enrichment.website_finder import resolve_website

logger = logging.getLogger(__name__)


def _pick_page_url(pages: list[CrawledPage], keyword: str) -> str | None:
    for page in pages:
        path = urlparse(page.url).path.lower()
        if keyword in path:
            return page.url
    return None


def _email_type(value: Any) -> EmailType:
    try:
        return EmailType(str(getattr(value, "value", value)))
    except ValueError:
        return EmailType.GENERIC


def _upsert_email_contact(
    db: Session,
    company: Company,
    lead: Lead | None,
    extracted: Any,
    *,
    source_provider: str,
) -> None:
    """Insert or update one contact. Works for crawler results and Hunter results alike."""
    email = str(extracted.email).strip().lower()
    if not email:
        return
    lookup = select(EmailContact).where(
        EmailContact.workspace_id == company.workspace_id,
        EmailContact.email == email,
    )
    if lead is not None:
        lookup = lookup.where(EmailContact.lead_id == lead.id)
    else:
        lookup = lookup.where(
            EmailContact.company_id == company.id,
            EmailContact.lead_id.is_(None),
        )
    existing = db.scalar(lookup)
    if existing:
        if not existing.source_url:
            existing.source_url = getattr(extracted, "source_url", None)
        return

    confidence = getattr(extracted, "confidence", None)
    email_type = _email_type(getattr(extracted, "email_type", EmailType.GENERIC))
    db.add(
        EmailContact(
            workspace_id=company.workspace_id,
            lead_id=lead.id if lead else None,
            company_id=company.id,
            email=email,
            email_type=email_type,
            confidence=float(confidence) if confidence is not None else 0.0,
            source_url=getattr(extracted, "source_url", None),
            source_provider=source_provider,
            is_role_based=bool(
                getattr(extracted, "is_role_based", email_type == EmailType.ROLE_BASED),
            ),
            is_personal=bool(getattr(extracted, "is_personal", email_type == EmailType.NAMED)),
        ),
    )


def _save_contacts(
    db: Session,
    company: Company,
    leads: list[Lead],
    contacts: list[Any],
    *,
    source_provider: str,
) -> None:
    for extracted in contacts:
        if leads:
            for lead in leads:
                _upsert_email_contact(db, company, lead, extracted, source_provider=source_provider)
        else:
            _upsert_email_contact(db, company, None, extracted, source_provider=source_provider)
        db.flush()


def _hunter_lookup(db: Session, company: Company) -> tuple[list[Any], str]:
    """Return ``(emails, note)``. Hunter problems never fail the enrichment."""
    from app.services.enrichment.email_discovery.factory import get_email_discovery_provider
    from app.services.enrichment.email_discovery.utils import extract_company_domain

    domain = extract_company_domain(company.website or company.domain)
    if not domain:
        return [], "Invalid or excluded domain for Hunter"

    from app.models.workspace import Workspace
    from app.services.billing.usage import record_usage, remaining

    try:
        provider = get_email_discovery_provider(db, company.workspace_id)
        if provider is None:
            return [], "Hunter not configured or disabled"
        workspace = db.get(Workspace, company.workspace_id)
        if workspace is not None and remaining(db, workspace, "daily_hunter_lookups") <= 0:
            return [], "Hunter daily lookup limit reached"
        results = list(provider.discover_by_domain(domain))
        record_usage(db, company.workspace_id, "daily_hunter_lookups")
        return results, ""
    except Exception as exc:
        logger.warning("Hunter lookup failed for company %s: %s", company.id, exc)
        return [], "Hunter lookup failed"


def _run_enrichment(db: Session, company: Company, website: str) -> None:
    headers = {"User-Agent": settings.enrichment_user_agent}
    with httpx.Client(headers=headers) as client:
        parser, fetched = fetch_robots_parser(website, client)
    company.robots_checked = fetched

    pages, crawl_error = crawl_company_site(
        website,
        robots_parser=parser,
        max_pages=settings.enrichment_max_pages,
    )
    if crawl_error:
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = crawl_error
        return
    if not pages:
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = "No pages could be fetched"
        return

    company.contact_page_url = _pick_page_url(pages, "contact") or company.contact_page_url
    company.about_page_url = (
        _pick_page_url(pages, "about") or _pick_page_url(pages, "team") or company.about_page_url
    )

    extracted_emails: list[Any] = []
    for page in pages:
        extracted_emails.extend(extract_emails_from_html(page.html, page.url))

    leads = list(company.leads or [])
    _save_contacts(db, company, leads, extracted_emails, source_provider="website")

    hunter_emails: list[Any] = []
    hunter_note = ""
    if not extracted_emails:
        hunter_emails, hunter_note = _hunter_lookup(db, company)
        _save_contacts(db, company, leads, hunter_emails, source_provider="hunter")

    total = len(extracted_emails) + len(hunter_emails)
    company.enrichment_status = EnrichmentStatus.COMPLETED
    if total:
        message = f"Enrichment completed. Found {total} public email(s)"
        if hunter_emails:
            message += f" (including {len(hunter_emails)} from Hunter)"
        for lead in leads:
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.ENRICHED
    else:
        message = f"Enrichment completed. Crawled {len(pages)} page(s); no public emails found."
    if hunter_note:
        message += f". {hunter_note}" if total else f" {hunter_note}"
    company.enrichment_message = message


def enrich_company_record(db: Session, company_id: int) -> Company:
    company = db.scalar(
        select(Company).where(Company.id == company_id).options(selectinload(Company.leads)),
    )
    if company is None:
        raise ValueError(f"Company {company_id} not found")

    website, domain = resolve_website(company.website)
    if not website:
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = "Company has no website URL"
        db.commit()
        return company

    company.website = website
    company.domain = domain or company.domain
    company.enrichment_status = EnrichmentStatus.IN_PROGRESS
    company.enrichment_message = "Enrichment in progress"
    db.commit()

    try:
        _run_enrichment(db, company, website)
    except UnsafeURLError:
        db.rollback()
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = "Website address is not allowed (private or reserved host)"
    except Exception:
        logger.exception("Enrichment failed for company %s", company_id)
        db.rollback()
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = "Enrichment failed unexpectedly. Please try again later."
    finally:
        if company.enrichment_status == EnrichmentStatus.IN_PROGRESS:
            company.enrichment_status = EnrichmentStatus.FAILED
            company.enrichment_message = "Enrichment did not finish"
        db.commit()

    db.refresh(company)
    return company
