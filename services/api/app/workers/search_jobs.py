from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.search_query import SearchQuery
from app.services.search.search_service import run_search_query_record
from app.core.celery_app import celery_app


@celery_app.task(name="search.run_query")
def run_search_query(search_query_id: int, limit: int = 10) -> dict[str, str]:
    db: Session = SessionLocal()
    try:
        search_query = db.get(SearchQuery, search_query_id)
        if search_query is None:
            return {"status": "failed", "reason": "search query not found"}
        run_search_query_record(db, search_query, limit=limit)
        return {"status": "completed", "search_query_id": str(search_query_id)}
    finally:
        db.close()
