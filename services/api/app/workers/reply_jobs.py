from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.user import User
from app.services.replies.sync import sync_mock_replies
from sqlalchemy import select


@celery_app.task(name="replies.sync")
def sync_replies(user_id: int | None = None) -> dict[str, int | str]:
    db = SessionLocal()
    try:
        if user_id is not None:
            synced = sync_mock_replies(db, user_id)
            return {"status": "ok", "synced": synced}

        users = db.scalars(select(User.id)).all()
        total = 0
        for uid in users:
            total += sync_mock_replies(db, uid)
        return {"status": "ok", "synced": total}
    finally:
        db.close()
