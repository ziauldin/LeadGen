from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.search_query import SearchQuery
from app.models.user import User
from scripts.seed import DEMO_EMAIL, seed


def _make_seed_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_seed_creates_demo_dataset():
    db = _make_seed_session()
    try:
        seed(db)
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert user is not None

        niches = db.scalars(select(Niche).where(Niche.user_id == user.id)).all()
        assert len(niches) == 1
        assert "WellPredict" in niches[0].name

        leads = db.scalars(select(Lead).where(Lead.niche_id == niches[0].id)).all()
        assert len(leads) >= 8

        campaigns = db.scalars(select(Campaign).where(Campaign.niche_id == niches[0].id)).all()
        assert len(campaigns) == 2

        searches = db.scalars(select(SearchQuery).where(SearchQuery.niche_id == niches[0].id)).all()
        assert len(searches) == 1
        assert searches[0].result_count >= 1
    finally:
        db.close()


def test_seed_is_idempotent_without_reset():
    db = _make_seed_session()
    try:
        seed(db)
        users_after_first = db.scalar(select(func.count(User.id))) or 0
        seed(db)
        users_after_second = db.scalar(select(func.count(User.id))) or 0
        assert users_after_first == users_after_second == 1
    finally:
        db.close()


def test_seed_reset_replaces_demo_data():
    db = _make_seed_session()
    try:
        seed(db)
        seed(db, force=True)
        users = db.scalar(select(func.count(User.id))) or 0
        assert users == 1
    finally:
        db.close()
