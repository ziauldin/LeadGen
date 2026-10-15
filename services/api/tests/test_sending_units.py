from datetime import UTC, date, datetime, timedelta

from app.models.campaign import Campaign
from app.models.provider_credential import ProviderCredential
from app.services.sending.schedule import schedule_for
from app.services.sending.warmup import daily_cap


def test_full_day_window_every_day():
    campaign = Campaign(
        niche_id=1,
        name="Test",
        daily_send_limit=20,
        sending_window_start="00:00",
        sending_window_end="23:59",
        sending_days=[0, 1, 2, 3, 4, 5, 6],
    )
    schedule = schedule_for(campaign, None, None)
    assert schedule.is_open(datetime(2026, 6, 26, 12, 0, tzinfo=UTC))
    assert schedule.is_open(datetime(2026, 6, 27, 12, 0, tzinfo=UTC))


def test_warmup_ramp_and_cap():
    started = datetime(2026, 6, 1, tzinfo=UTC)
    credential = ProviderCredential(
        warmup_enabled=True,
        warmup_started_at=started,
        warmup_start_volume=10,
        warmup_daily_increment=5,
        warmup_max=40,
    )
    assert daily_cap(credential, date(2026, 6, 1)) == 10
    assert daily_cap(credential, date(2026, 6, 3)) == 20
    assert daily_cap(credential, (started + timedelta(days=30)).date()) == 40
    credential.warmup_enabled = False
    assert daily_cap(credential, date(2026, 6, 3)) is None
