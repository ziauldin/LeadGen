from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.enums import EnrichmentStatus, LeadStatus
from app.models.lead import Lead
from app.services.enrichment.email_extractor import extract_emails_from_html
from app.services.enrichment.robots_checker import fetch_robots_parser
from app.services.enrichment.website_crawler import crawl_company_site
from app.services.enrichment.website_finder import resolve_website
from app.core.config import settings

import httpx


def _pick_page_url(pages, keyword: str) -> str | None:
    for page in pages:
        path = urlparse(page.url).path.lower()
        if keyword in path:
            return page.url
    return None


def _upsert_email_contact(
    db: Session,
    company: Company,
    lead: Lead | None,
    extracted,
) -> None:
    existing = db.scalar(
        select(EmailContact).where(
            EmailContact.company_id == company.id,
            EmailContact.email == extracted.email,
        ),
    )
    if existing:
        if lead and existing.lead_id is None:
            existing.lead_id = lead.id
        if not existing.source_url:
            existing.source_url = extracted.source_url
        return

    db.add(
        EmailContact(
            lead_id=lead.id if lead else None,
            company_id=company.id,
            email=extracted.email,
            email_type=extracted.email_type,
            confidence=extracted.confidence,
            source_url=extracted.source_url,
            is_role_based=extracted.is_role_based,
            is_personal=extracted.is_personal,
        ),
    )


def enrich_company_record(db: Session, company_id: int) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.leads)),
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

    headers = {"User-Agent": settings.enrichment_user_agent}
    try:
        with httpx.Client(headers=headers, follow_redirects=True) as client:
            parser, fetched = fetch_robots_parser(website, client)
            company.robots_checked = fetched or True

        pages, crawl_error = crawl_company_site(website)
        if crawl_error:
            company.enrichment_status = EnrichmentStatus.FAILED
            company.enrichment_message = crawl_error
            db.commit()
            return company

        if not pages:
            company.enrichment_status = EnrichmentStatus.FAILED
            company.enrichment_message = "No pages could be fetched"
            db.commit()
            return company

        company.contact_page_url = _pick_page_url(pages, "contact") or company.contact_page_url
        company.about_page_url = (
            _pick_page_url(pages, "about") or _pick_page_url(pages, "team") or company.about_page_url
        )

        extracted_emails = []
        for page in pages:
            extracted_emails.extend(extract_emails_from_html(page.html, page.url))

        leads = list(company.leads or [])
        if extracted_emails:
            for extracted in extracted_emails:
                if leads:
                    for lead in leads:
                        _upsert_email_contact(db, company, lead, extracted)
                else:
                    _upsert_email_contact(db, company, None, extracted)

    except Exception as exc:
        company.enrichment_status = EnrichmentStatus.FAILED
        company.enrichment_message = f"Enrichment failed: {exc}"
        db.commit()
        db.refresh(company)
        return company

    hunter_emails = []
    hunter_skipped_msg = ""
    try:
        from app.models.lead import Lead
        from app.models.niche import Niche
        
        user_id = None
        if company.leads:
            user_id = db.scalar(
                select(Niche.user_id)
                .join(Lead, Lead.niche_id == Niche.id)
                .where(Lead.id == company.leads[0].id)
            )

        from app.services.enrichment.email_discovery.factory import get_email_discovery_provider
        from app.services.enrichment.email_discovery.utils import extract_company_domain
        
        domain_for_hunter = extract_company_domain(company.website or company.domain)
        if domain_for_hunter:
            provider = get_email_discovery_provider(db, user_id)
            if provider:
                # We can call it even if we extracted emails, to supplement them
                # But to preserve API quota, maybe we check if extracted_emails is empty?
                # The user wrote: "First run existing public website crawler... If no useful emails are found, call Hunter using the company domain."
                if not extracted_emails:
                    hunter_emails = provider.discover_by_domain(domain_for_hunter)
            else:
                hunter_skipped_msg = "Hunter not configured or disabled"
        else:
            hunter_skipped_msg = "Invalid or excluded domain for Hunter"
            
    except Exception as exc:
        # Hunter errors should not break the pipeline
        hunter_skipped_msg = f"Hunter lookup skipped or failed: {str(exc).split(':')[-1].strip()}"

    if hunter_emails:
        for extracted in hunter_emails:
            if leads:
                for lead in leads:
                    _upsert_email_contact(db, company, lead, extracted)
            else:
                _upsert_email_contact(db, company, None, extracted)

    total_emails = len(extracted_emails) + len(hunter_emails)
    if total_emails > 0:
        company.enrichment_status = EnrichmentStatus.COMPLETED
        msg = f"Enrichment completed. Found {total_emails} public email(s)"
        if hunter_emails:
            msg += f" (including {len(hunter_emails)} from Hunter)"
        if hunter_skipped_msg:
            msg += f". {hunter_skipped_msg}"
        company.enrichment_message = msg
        
        for lead in leads:
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.ENRICHED
    else:
        company.enrichment_status = EnrichmentStatus.COMPLETED
        msg = f"Enrichment completed. Crawled {len(pages)} page(s); no public emails found."
        if hunter_skipped_msg:
            msg += f" {hunter_skipped_msg}"
        company.enrichment_message = msg

    db.commit()
    db.refresh(company)
    return company
