from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import SearchProvider, SearchStatus
from app.models.niche import Niche
from app.models.search_query import SearchQuery
from app.models.user import User
from app.services.search.provider_factory import get_active_search_provider_name
from app.schemas.search import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    RunSearchRequest,
    SaveSearchResultsRequest,
    SaveSearchResultsResponse,
    SearchQueryRead,
    SearchResultItem,
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

    provider = search.provider.value if hasattr(search.provider, "value") else str(search.provider)
    search_status = search.status.value if hasattr(search.status, "value") else str(search.status)

    return SearchQueryRead(
        id=search.id,
        niche_id=search.niche_id,
        query=search.query,
        provider=provider,
        status=search_status,
        result_count=search.result_count,
        results=results,
        created_at=search.created_at,
    )


@router.post("/generate-queries", response_model=GenerateQueriesResponse)
def generate_queries(
    payload: GenerateQueriesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateQueriesResponse:
    niche = db.scalar(
        select(Niche).where(Niche.id == payload.niche_id, Niche.user_id == current_user.id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    queries = generate_search_queries(niche)
    return GenerateQueriesResponse(niche_id=niche.id, queries=queries)


@router.post("/run", response_model=SearchQueryRead, status_code=status.HTTP_201_CREATED)
def run_search(
    payload: RunSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchQueryRead:
    niche = db.scalar(
        select(Niche).where(Niche.id == payload.niche_id, Niche.user_id == current_user.id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    provider_key = get_active_search_provider_name(db, current_user.id)
    try:
        provider = SearchProvider(provider_key)
    except ValueError:
        provider = SearchProvider.MOCK

    search_query = SearchQuery(
        niche_id=niche.id,
        query=payload.query.strip(),
        provider=provider,
        status=SearchStatus.PENDING,
        results=[],
    )
    db.add(search_query)
    db.commit()
    db.refresh(search_query)

    search_query = run_search_query_record(db, search_query, limit=payload.limit)
    return _serialize_search(search_query)


@router.get("/{search_id}", response_model=SearchQueryRead)
def get_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchQueryRead:
    search = db.scalar(
        select(SearchQuery)
        .join(Niche, SearchQuery.niche_id == Niche.id)
        .where(SearchQuery.id == search_id, Niche.user_id == current_user.id),
    )
    if search is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return _serialize_search(search)


@router.post("/{search_id}/save-results", response_model=SaveSearchResultsResponse)
def save_results(
    search_id: int,
    payload: SaveSearchResultsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaveSearchResultsResponse:
    search = db.scalar(
        select(SearchQuery)
        .join(Niche, SearchQuery.niche_id == Niche.id)
        .where(SearchQuery.id == search_id, Niche.user_id == current_user.id),
    )
    if search is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")

    niche = db.get(Niche, search.niche_id)
    assert niche is not None

    created, skipped = save_search_results(
        db,
        search,
        niche,
        selected_urls=payload.selected_urls,
    )
    return SaveSearchResultsResponse(created=created, skipped=skipped)
