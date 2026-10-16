"""Shared paging and sorting for list endpoints.

``sort`` is a comma-separated list of allowed field names; a leading ``-`` sorts descending,
e.g. ``sort=-score,full_name``. Unknown fields are a 400, so typos don't silently reorder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Query, status
from sqlalchemy import ColumnElement


@dataclass(frozen=True)
class PageParams:
    skip: int
    limit: int
    sort: str | None


def page_params(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    sort: str | None = Query(default=None, max_length=200, pattern=r"^[A-Za-z_,\-]*$"),
) -> PageParams:
    return PageParams(skip=skip, limit=limit, sort=sort)


def order_by(
    sort: str | None,
    allowed: dict[str, Any],
    default: list[ColumnElement[Any]],
    tiebreaker: Any,
) -> list[ColumnElement[Any]]:
    if not sort:
        return [*default, tiebreaker.desc()]
    clauses: list[ColumnElement[Any]] = []
    for raw in sort.split(","):
        name = raw.strip()
        if not name:
            continue
        descending = name.startswith("-")
        key = name.lstrip("-")
        column = allowed.get(key)
        if column is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can't sort by {key!r}. Allowed: {', '.join(sorted(allowed))}",
            )
        clauses.append(column.desc() if descending else column.asc())
    return [*clauses, tiebreaker.desc()]
