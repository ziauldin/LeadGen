from typing import Literal

from pydantic import BaseModel, Field

MAX_BULK = 500


class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int


class BulkItemResult(BaseModel):
    id: int
    status: Literal["ok", "failed", "skipped"]
    detail: str | None = None


class BulkResult(BaseModel):
    """Per-item outcome of a bulk action. One bad item never fails the whole request."""

    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[BulkItemResult] = Field(default_factory=list)

    def ok(self, item_id: int, detail: str | None = None) -> None:
        self.succeeded += 1
        self.results.append(BulkItemResult(id=item_id, status="ok", detail=detail))

    def fail(self, item_id: int, detail: str) -> None:
        self.failed += 1
        self.results.append(BulkItemResult(id=item_id, status="failed", detail=detail))

    def skip(self, item_id: int, detail: str) -> None:
        self.skipped += 1
        self.results.append(BulkItemResult(id=item_id, status="skipped", detail=detail))


class BulkIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=MAX_BULK)
