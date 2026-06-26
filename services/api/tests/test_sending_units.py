from datetime import UTC, datetime

from app.services.sending.gate import _within_sending_window
from app.models.campaign import Campaign


def test_within_sending_window_full_day():
    campaign = Campaign(
        niche_id=1,
        name="Test",
        daily_send_limit=20,
        sending_window_start="00:00",
        sending_window_end="23:59",
    )
    assert _within_sending_window(campaign, datetime(2026, 6, 26, 12, 0, tzinfo=UTC)) is True
