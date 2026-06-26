from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int
