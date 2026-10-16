import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LeadStatus, SearchProvider, SearchStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.search_query import SearchQuery
from app.services.developer import events as webhook_events
from app.services.search.base import SearchResult
from app.services.search.provider_factory import get_search_provider_for_workspace

logger = logging.getLogger(__name__)


def _public_search_error(exc: Exception) -> str:
    """Describe a provider failure without leaking keys or internal details."""
    from app.services.search.external_providers import ProviderConfigurationError

    if isinstance(exc, ProviderConfigurationError):
        return str(exc)
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in {401, 403}:
        return "The search provider rejected the API key. Check it in Settings > Providers."
    if status == 429:
        return "The search provider rate limit was reached. Try again later."
    return "The search provider request failed. Try again later."


def run_search_query_record(
    db: Session,
    search_query: SearchQuery,
    limit: int = 10,
    provider_name: str | None = None,
) -> SearchQuery:
    search_query.status = SearchStatus.RUNNING
    db.commit()

    try:
        provider = get_search_provider_for_workspace(db, search_query.workspace_id, provider_name)
        raw_results = provider.search(search_query.query, limit=limit)
        search_query.results = [item.to_dict() for item in raw_results]
        search_query.result_count = len(raw_results)
        search_query.status = SearchStatus.COMPLETED
        search_query.provider = SearchProvider(provider.provider_name)
    except Exception as exc:
        logger.warning("Search %s failed: %s", search_query.id, exc)
        search_query.status = SearchStatus.FAILED
        search_query.results = [{"error": _public_search_error(exc)}]
        search_query.result_count = 0

    db.commit()
    db.refresh(search_query)
    return search_query


def _parse_name_from_title(title: str) -> tuple[str, str | None]:
    if " at " in title:
        name, rest = title.split(" at ", 1)
        job = rest.split("—")[0].split("-")[0].strip()
        return name.strip(), job or None
    if " - " in title:
        parts = title.split(" - ", 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
    return title.strip(), None


def _parse_role_from_query(query: str) -> str | None:
    match = re.search(r'"([^"]+)"', query)
    return match.group(1) if match else None


def save_search_results(
    db: Session,
    search_query: SearchQuery,
    niche: Niche,
    selected_urls: list[str] | None = None,
) -> tuple[int, int]:
    stored = [
        SearchResult.from_dict(item) for item in (search_query.results or []) if "url" in item
    ]
    if selected_urls is not None:
        selected_set = set(selected_urls)
        stored = [item for item in stored if item.url in selected_set]

    created = 0
    skipped = 0
    provider_name = (
        search_query.provider.value
        if hasattr(search_query.provider, "value")
        else str(search_query.provider)
    )
    default_role = _parse_role_from_query(search_query.query)
    compliance_note = (
        f"Discovered via {provider_name} search on {search_query.created_at.date().isoformat()}. "
        f"Query: {search_query.query}"
    )

    seen: set[str] = set()
    for item in stored:
        if not item.url or item.url in seen:
            skipped += 1
            continue
        seen.add(item.url)

        existing = db.scalar(
            select(Lead.id).where(
                Lead.workspace_id == niche.workspace_id,
                Lead.niche_id == niche.id,
                Lead.linkedin_url == item.url,
            ),
        )
        if existing:
            skipped += 1
            continue

        full_name, parsed_title = _parse_name_from_title(item.title)
        lead = Lead(
            workspace_id=niche.workspace_id,
            niche_id=niche.id,
            full_name=full_name or "Unknown",
            job_title=parsed_title or default_role,
            linkedin_url=item.url,
            source_url=item.url,
            source_provider=provider_name,
            compliance_source_note=compliance_note,
            status=LeadStatus.NEW,
        )
        db.add(lead)
        db.flush()
        webhook_events.lead_created(db, lead)
        created += 1

    db.commit()
    return created, skipped
