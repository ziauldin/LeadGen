from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.tenancy import system_session, workspace_scope
from app.models.company import Company
from app.services.enrichment.enricher import enrich_company_record


@celery_app.task(name="enrichment.enrich_company")
def enrich_company(company_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        with system_session(db):  # find which workspace the company belongs to
            company = db.get(Company, company_id)
        if company is None:
            return {"status": "missing", "company_id": str(company_id), "message": ""}
        with workspace_scope(db, company.workspace_id):
            company = enrich_company_record(db, company_id)
            return {
                "status": str(company.enrichment_status),
                "company_id": str(company_id),
                "message": company.enrichment_message or "",
            }
    finally:
        db.close()
