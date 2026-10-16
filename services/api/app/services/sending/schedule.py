"""Sending windows, days and "today" in the campaign's own timezone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.workspace import DEFAULT_SENDING_DAYS, Workspace, WorkspaceSettings

ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]


@dataclass(frozen=True)
class SendingSchedule:
    tz: ZoneInfo
    start: time
    end: time
    days: frozenset[int]

    def local(self, now: datetime) -> datetime:
        return now.astimezone(self.tz)

    def local_today(self, now: datetime) -> date:
        return self.local(now).date()

    def day_bounds_utc(self, now: datetime) -> tuple[datetime, datetime]:
        """Start and end of the campaign's local day, in UTC."""
        local_midnight = datetime.combine(self.local_today(now), time.min, tzinfo=self.tz)
        start = local_midnight.astimezone(UTC)
        return start, (local_midnight + timedelta(days=1)).astimezone(UTC)

    def is_open(self, now: datetime) -> bool:
        local = self.local(now)
        if local.weekday() not in self.days:
            return False
        current = local.time()
        if self.start <= self.end:
            return self.start <= current <= self.end
        return current >= self.start or current <= self.end  # window crosses midnight

    def next_open(self, now: datetime) -> datetime:
        """The next moment (UTC) the window opens; ``now`` if it is already open."""
        if self.is_open(now):
            return now
        local = self.local(now)
        for offset in range(0, 8):
            day = local.date() + timedelta(days=offset)
            if day.weekday() not in self.days:
                continue
            candidate = datetime.combine(day, self.start, tzinfo=self.tz)
            if candidate > local:
                return candidate.astimezone(UTC)
        # No sending days configured: try again tomorrow so nothing is lost.
        return (local + timedelta(days=1)).astimezone(UTC)

    def next_day_open(self, now: datetime) -> datetime:
        """The window start on the next sending day after today (for daily limits)."""
        local = self.local(now)
        for offset in range(1, 9):
            day = local.date() + timedelta(days=offset)
            if day.weekday() in self.days:
                return datetime.combine(day, self.start, tzinfo=self.tz).astimezone(UTC)
        return (local + timedelta(days=1)).astimezone(UTC)


def _parse_hhmm(value: str | None, fallback: str) -> time:
    raw = value or fallback
    hour, minute = raw.split(":")
    return time(hour=int(hour), minute=int(minute))


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def schedule_for(
    campaign: Campaign,
    workspace: Workspace | None,
    workspace_settings: WorkspaceSettings | None,
) -> SendingSchedule:
    tz = _zone(campaign.timezone or (workspace.timezone if workspace else None))
    start = _parse_hhmm(
        campaign.sending_window_start,
        workspace_settings.default_sending_window_start
        if workspace_settings
        else settings.default_sending_window_start,
    )
    end = _parse_hhmm(
        campaign.sending_window_end,
        workspace_settings.default_sending_window_end
        if workspace_settings
        else settings.default_sending_window_end,
    )
    days = campaign.sending_days
    if days is None:
        days = workspace_settings.sending_days if workspace_settings else DEFAULT_SENDING_DAYS
    return SendingSchedule(tz=tz, start=start, end=end, days=frozenset(int(d) for d in days))
