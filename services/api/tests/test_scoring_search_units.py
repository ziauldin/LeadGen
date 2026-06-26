from app.services.scoring.lead_score import score_lead
from app.services.scoring.rules import SCORING_RULES
from app.services.search.mock_provider import MockSearchProvider
from app.services.search.query_generator import generate_search_queries


def test_mock_search_provider_returns_linkedin_urls():
    provider = MockSearchProvider()
    results = provider.search(
        'site:linkedin.com/in "Quality Manager" "Food Manufacturing" "UK"',
        limit=3,
    )
    assert len(results) == 3
    assert all(r.provider == "mock" for r in results)
    assert all("linkedin.com/in/" in r.url for r in results)


def test_scoring_rules_count():
    assert len(SCORING_RULES) == 9
