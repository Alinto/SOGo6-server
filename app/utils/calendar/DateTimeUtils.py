from __future__ import annotations

# pylint R0801 (duplicate-code) may be reported here as a false positive:
# short common patterns (e.g. "if not rows: return None") in unrelated files
# can trigger the similarity checker against this module.
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def to_utc(dt: datetime | date) -> datetime:
    """Convert a datetime or date to a UTC-aware datetime.

    Naive datetimes are assumed UTC. Date-only values are converted to midnight UTC.
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def resolve_tz(tz_name: str) -> ZoneInfo:
    """Return a ZoneInfo for the given IANA timezone name, falling back to UTC on unknown names."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("UTC")
