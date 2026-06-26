from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.enrichment.enricher import enrich_company_record


@celery_app.task(name="enrichment.enrich_company")
def enrich_company(company_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        company = enrich_company_record(db, company_id)
        return {
            "status": company.enrichment_status.value
            if hasattr(company.enrichment_status, "value")
            else str(company.enrichment_status),
            "company_id": str(company_id),
            "message": company.enrichment_message or "",
        }
    finally:
        db.close()
