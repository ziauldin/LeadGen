from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateQueriesRequest(BaseModel):
    niche_id: int


class GenerateQueriesResponse(BaseModel):
    niche_id: int
    queries: list[str]


class RunSearchRequest(BaseModel):
    niche_id: int
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    provider: str


class SearchQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    query: str
    provider: str
    status: str
    result_count: int
    results: list[SearchResultItem | dict]
    created_at: datetime


class SaveSearchResultsRequest(BaseModel):
    selected_urls: list[str] | None = None


class SaveSearchResultsResponse(BaseModel):
    created: int
    skipped: int
