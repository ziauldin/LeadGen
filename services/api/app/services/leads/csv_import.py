import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.enums import EmailType, LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.services.companies.helpers import extract_domain, normalize_website

CSV_IMPORT_COLUMNS = [
    "full_name",
    "job_title",
    "company",
    "website",
    "linkedin_url",
    "email",
    "source_url",
    "compliance_source_note",
    "niche",
]

CSV_EXPORT_COLUMNS = [
    "full_name",
    "job_title",
    "company",
    "website",
    "email",
    "score",
    "status",
    "source_url",
    "compliance_source_note",
]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _resolve_niche(db: Session, user: User, niche_value: str | None) -> Niche | None:
    if not niche_value or not niche_value.strip():
        return db.scalar(select(Niche).where(Niche.user_id == user.id).limit(1))

    niche_value = niche_value.strip()
    if niche_value.isdigit():
        return db.scalar(
            select(Niche).where(Niche.id == int(niche_value), Niche.user_id == user.id),
        )

    return db.scalar(
        select(Niche).where(Niche.name.ilike(niche_value), Niche.user_id == user.id),
    )


def _get_or_create_company(db: Session, name: str, website: str | None) -> Company:
    domain = extract_domain(website)
    company: Company | None = None

    if domain:
        company = db.scalar(select(Company).where(Company.domain == domain))

    if company is None and name:
        company = db.scalar(select(Company).where(Company.name.ilike(name.strip())))

    if company is None:
        company = Company(
            name=name.strip(),
            website=normalize_website(website),
            domain=domain,
        )
        db.add(company)
        db.flush()
        return company

    if website and not company.website:
        company.website = normalize_website(website)
    if domain and not company.domain:
        company.domain = domain
    if name and company.name != name.strip():
        company.name = name.strip()

    db.flush()
    return company


def _find_existing_lead(
    db: Session,
    niche_id: int,
    linkedin_url: str | None,
    full_name: str,
    company_id: int | None,
) -> Lead | None:
    if linkedin_url and linkedin_url.strip():
        return db.scalar(
            select(Lead).where(
                Lead.niche_id == niche_id,
                Lead.linkedin_url == linkedin_url.strip(),
            ),
        )

    if company_id:
        return db.scalar(
            select(Lead).where(
                Lead.niche_id == niche_id,
                Lead.full_name.ilike(full_name.strip()),
                Lead.company_id == company_id,
            ),
        )

    return db.scalar(
        select(Lead).where(
            Lead.niche_id == niche_id,
            Lead.full_name.ilike(full_name.strip()),
            Lead.company_id.is_(None),
        ),
    )


def import_leads_from_csv(db: Session, user: User, file_content: str) -> ImportResult:
    result = ImportResult()
    reader = csv.DictReader(io.StringIO(file_content))

    if not reader.fieldnames:
        result.errors.append("CSV file is empty or missing a header row")
        return result

    missing = [col for col in CSV_IMPORT_COLUMNS if col not in reader.fieldnames]
    if missing:
        result.errors.append(f"Missing required columns: {', '.join(missing)}")
        return result

    for row_num, row in enumerate(reader, start=2):
        full_name = (row.get("full_name") or "").strip()
        if not full_name:
            result.skipped += 1
            result.errors.append(f"Row {row_num}: full_name is required")
            continue

        niche = _resolve_niche(db, user, row.get("niche"))
        if niche is None:
            result.skipped += 1
            result.errors.append(f"Row {row_num}: niche not found for user")
            continue

        company_name = (row.get("company") or "").strip()
        website = (row.get("website") or "").strip() or None
        company = None
        if company_name:
            company = _get_or_create_company(db, company_name, website)

        linkedin_url = (row.get("linkedin_url") or "").strip() or None
        existing = _find_existing_lead(
            db,
            niche.id,
            linkedin_url,
            full_name,
            company.id if company else None,
        )

        email = (row.get("email") or "").strip().lower() or None
        source_url = (row.get("source_url") or "").strip() or None
        compliance_note = (row.get("compliance_source_note") or "").strip() or None

        if existing:
            existing.full_name = full_name
            existing.job_title = (row.get("job_title") or "").strip() or existing.job_title
            existing.linkedin_url = linkedin_url or existing.linkedin_url
            existing.source_url = source_url or existing.source_url
            existing.compliance_source_note = compliance_note or existing.compliance_source_note
            if company:
                existing.company_id = company.id
            lead = existing
            result.updated += 1
        else:
            lead = Lead(
                niche_id=niche.id,
                full_name=full_name,
                job_title=(row.get("job_title") or "").strip() or None,
                linkedin_url=linkedin_url,
                source_url=source_url,
                source_provider="csv_import",
                company_id=company.id if company else None,
                status=LeadStatus.NEW,
                compliance_source_note=compliance_note,
            )
            db.add(lead)
            db.flush()
            result.created += 1

        if email:
            contact = db.scalar(
                select(EmailContact).where(
                    EmailContact.lead_id == lead.id,
                    EmailContact.email == email,
                ),
            )
            if contact is None:
                db.add(
                    EmailContact(
                        lead_id=lead.id,
                        company_id=company.id if company else None,
                        email=email,
                        email_type=EmailType.GENERIC,
                        source_url=source_url,
                        confidence=0.8,
                    ),
                )

    db.commit()
    return result


def export_leads_to_csv(db: Session, user: User, niche_id: int | None = None) -> str:
    query = (
        select(Lead)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == user.id)
        .options(
            selectinload(Lead.company),
            selectinload(Lead.email_contacts),
        )
        .order_by(Lead.updated_at.desc())
    )
    if niche_id is not None:
        query = query.where(Lead.niche_id == niche_id)

    leads = db.scalars(query).all()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_EXPORT_COLUMNS)
    writer.writeheader()

    for lead in leads:
        primary_email = next((c.email for c in lead.email_contacts), "")
        writer.writerow(
            {
                "full_name": lead.full_name,
                "job_title": lead.job_title or "",
                "company": lead.company.name if lead.company else "",
                "website": lead.company.website if lead.company else "",
                "email": primary_email,
                "score": lead.score,
                "status": lead.status.value if hasattr(lead.status, "value") else lead.status,
                "source_url": lead.source_url or "",
                "compliance_source_note": lead.compliance_source_note or "",
            },
        )

    return output.getvalue()
