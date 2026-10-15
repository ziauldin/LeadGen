"""Warm-up: ramp a new sending domain/account up slowly to protect its reputation."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.provider_credential import ProviderCredential


def daily_cap(credential: ProviderCredential | None, today: date) -> int | None:
    """Maximum sends today through this credential, or None when warm-up is off."""
    if credential is None or not credential.warmup_enabled or credential.warmup_started_at is None:
        return None
    started = credential.warmup_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    days = max(0, (today - started.astimezone(UTC).date()).days)
    cap = credential.warmup_start_volume + credential.warmup_daily_increment * days
    if credential.warmup_max is not None:
        cap = min(cap, credential.warmup_max)
    return max(0, cap)


def warmup_finished(credential: ProviderCredential, now: datetime | None = None) -> bool:
    if not credential.warmup_enabled or credential.warmup_max is None:
        return False
    cap = daily_cap(credential, (now or datetime.now(UTC)).date())
    return cap is not None and cap >= credential.warmup_max
