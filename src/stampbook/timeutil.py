"""Pure time helpers. All times are naive UTC with whole-second precision."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
_TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class StampbookError(Exception):
    """Error carrying a process exit code."""

    exit_code = 1


class DomainError(StampbookError):
    exit_code = 1


class UsageError(StampbookError):
    exit_code = 2


def parse_timestamp(value: str) -> datetime:
    """Parse YYYY-MM-DDTHH:MM:SS strictly; raise ValueError otherwise."""
    if not _TS_RE.fullmatch(value):
        raise ValueError(value)
    return datetime.strptime(value, TS_FORMAT)


def format_timestamp(moment: datetime) -> str:
    return moment.strftime(TS_FORMAT)


def format_display(moment: datetime) -> str:
    """YYYY-MM-DD HH:MM:SS."""
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def format_clock(moment: datetime) -> str:
    """HH:MM."""
    return moment.strftime("%H:%M")


def parse_now(value: str) -> datetime:
    try:
        return parse_timestamp(value)
    except ValueError:
        raise UsageError(f"invalid STAMPBOOK_NOW: {value}") from None


def parse_date(value: str) -> date:
    if not _DATE_RE.fullmatch(value):
        raise UsageError(f"invalid date: {value}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise UsageError(f"invalid date: {value}") from None


def format_duration(seconds: int) -> str:
    minutes = max(int(seconds), 0) // 60
    hours, mins = divmod(minutes, 60)
    if hours >= 1:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day)


def range_bounds(first: date, last: date) -> tuple[datetime, datetime]:
    """Half-open range [first 00:00:00, last 00:00:00 + 1 day)."""
    return day_start(first), day_start(last) + timedelta(days=1)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def overlaps(
    start: datetime, end: datetime, range_start: datetime, range_end: datetime
) -> bool:
    """Overlap rule; `end` must already be `now` for a running entry."""
    if start >= range_end:
        return False
    return end > range_start or (end == start and start >= range_start)


def clipped_seconds(
    start: datetime, end: datetime, range_start: datetime, range_end: datetime
) -> int:
    """Whole seconds of [start, end] inside [range_start, range_end)."""
    lo = max(start, range_start)
    hi = min(end, range_end)
    if hi <= lo:
        return 0
    return int((hi - lo).total_seconds())
