from app.models.lead import Lead
from app.schemas.lead import CompanySummary, LeadRead


def serialize_lead(lead: Lead) -> LeadRead:
    primary_email = lead.email_contacts[0].email if lead.email_contacts else None
    company = CompanySummary.model_validate(lead.company) if lead.company else None
    return LeadRead(
        id=lead.id,
        niche_id=lead.niche_id,
        full_name=lead.full_name,
        job_title=lead.job_title,
        linkedin_url=lead.linkedin_url,
        source_url=lead.source_url,
        source_provider=lead.source_provider,
        company_id=lead.company_id,
        status=lead.status,
        score=lead.score,
        qualification_notes=lead.qualification_notes,
        compliance_source_note=lead.compliance_source_note,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        company=company,
        primary_email=primary_email,
    )
