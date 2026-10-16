"""Queue company enrichment with quota checks, for single and bulk requests."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError, ValidationFailedError
from app.models.company import Company
from app.models.enums import EnrichmentStatus
from app.models.workspace import Workspace
from app.services.billing.usage import check_quota, record_usage

logger = logging.getLogger(__name__)


def queue_enrichment(db: Session, workspace: Workspace, company: Company) -> str:
    """Charge one enrichment and hand the company to a worker. Returns "queued"."""
    from app.workers.enrichment_jobs import enrich_company

    if not company.website:
        raise ValidationFailedError("Company has no website to enrich")
    check_quota(db, workspace, "daily_enrichments")
    previous_status = company.enrichment_status
    previous_message = company.enrichment_message
    record_usage(db, workspace.id, "daily_enrichments")
    company.enrichment_status = EnrichmentStatus.IN_PROGRESS
    company.enrichment_message = "Enrichment queued"
    db.commit()
    try:
        enrich_company.delay(company.id)
    except Exception as exc:
        logger.warning("Could not queue enrichment for company %s: %s", company.id, exc)
        company.enrichment_status = previous_status
        company.enrichment_message = previous_message
        db.commit()
        raise ServiceUnavailableError(
            "Background workers are unavailable. Try again shortly, or run it inline.",
        ) from None
    return "queued"
