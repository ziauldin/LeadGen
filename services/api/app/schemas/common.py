from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int
