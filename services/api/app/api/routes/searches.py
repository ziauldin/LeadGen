from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.core.errors import ValidationFailedError
from app.core.tenancy import WorkspaceContext
from app.models.enums import ProviderName, SearchProvider, SearchStatus
from app.models.niche import Niche
from app.models.search_query import SearchQuery
from app.schemas.search import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    RunSearchRequest,
    SaveSearchResultsRequest,
    SaveSearchResultsResponse,
    SearchQueryRead,
    SearchResultItem,
)
from app.services.search.provider_factory import (
    find_search_credential,
    get_active_search_provider_name,
)
from app.services.search.query_generator import generate_search_queries
from app.services.search.search_service import run_search_query_record, save_search_results

router = APIRouter(prefix="/searches", tags=["searches"])


def _serialize_search(search: SearchQuery) -> SearchQueryRead:
    results: list[SearchResultItem | dict] = []
    for item in search.results or []:
        if isinstance(item, dict) and "url" in item:
            results.append(SearchResultItem(**item))
        else:
            results.append(item)

    return SearchQueryRead(
        id=search.id,
        niche_id=search.niche_id,
        query=search.query,
        provider=str(search.provider),
        status=str(search.status),
        result_count=search.result_count,
        results=results,
        created_at=search.created_at,
    )


def _get_niche(db: Session, niche_id: int, ctx: WorkspaceContext) -> Niche:
    niche = db.scalar(
        select(Niche).where(Niche.id == niche_id, Niche.workspace_id == ctx.workspace_id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    return niche


def _get_search(db: Session, search_id: int, ctx: WorkspaceContext) -> SearchQuery:
    search = db.scalar(
        select(SearchQuery).where(
            SearchQuery.id == search_id,
            SearchQuery.workspace_id == ctx.workspace_id,
        ),
    )
    if search is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return search


@router.post("/generate-queries", response_model=GenerateQueriesResponse)
def generate_queries(
    payload: GenerateQueriesRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> GenerateQueriesResponse:
    niche = _get_niche(db, payload.niche_id, ctx)
    return GenerateQueriesResponse(niche_id=niche.id, queries=generate_search_queries(niche))


@router.post("/run", response_model=SearchQueryRead, status_code=status.HTTP_201_CREATED)
def run_search(
    payload: RunSearchRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> SearchQueryRead:
    niche = _get_niche(db, payload.niche_id, ctx)

    if payload.provider and payload.provider != ProviderName.MOCK.value:
        valid = payload.provider in {name.value for name in ProviderName}
        if not valid or find_search_credential(db, ctx.workspace_id, payload.provider) is None:
            raise ValidationFailedError(
                f"No {payload.provider} search account is set up. Add it in Settings → Providers.",
            )
    provider_key = payload.provider or get_active_search_provider_name(db, ctx.workspace_id)
    try:
        provider = SearchProvider(provider_key)
    except ValueError:
        provider = SearchProvider.MOCK

    search_query = SearchQuery(
        workspace_id=ctx.workspace_id,
        niche_id=niche.id,
        query=payload.query.strip(),
        provider=provider,
        status=SearchStatus.PENDING,
        results=[],
    )
    db.add(search_query)
    db.commit()
    db.refresh(search_query)

    search_query = run_search_query_record(
        db, search_query, limit=payload.limit, provider_name=payload.provider
    )
    return _serialize_search(search_query)


@router.get("/{search_id}", response_model=SearchQueryRead)
def get_search(
    search_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> SearchQueryRead:
    return _serialize_search(_get_search(db, search_id, ctx))


@router.post("/{search_id}/save-results", response_model=SaveSearchResultsResponse)
def save_results(
    search_id: int,
    payload: SaveSearchResultsRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> SaveSearchResultsResponse:
    search = _get_search(db, search_id, ctx)
    niche = _get_niche(db, search.niche_id, ctx)
    created, skipped = save_search_results(db, search, niche, selected_urls=payload.selected_urls)
    return SaveSearchResultsResponse(created=created, skipped=skipped)
