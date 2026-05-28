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


def anchor_to_utc(dt: datetime, default_tz_name: str | None) -> datetime:
    """Convert a datetime to UTC, anchoring naive (floating) values to ``default_tz_name``.

    A tz-aware value is converted to UTC directly. A naive value is interpreted in
    ``default_tz_name`` when provided (RFC 5545 floating time anchored to a calendar/user
    zone), otherwise assumed to be UTC (same behaviour as :func:`to_utc`).
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    if default_tz_name:
        return dt.replace(tzinfo=resolve_tz(default_tz_name)).astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def fmt_dt(dt: datetime) -> str:
    """Format a datetime as ISO 8601 UTC with millisecond precision ending in Z.

    Naive datetimes are assumed UTC. Non-UTC datetimes are converted to UTC first.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def apply_tz(dt: datetime, tz_name: str) -> str | None:
    """Convert dt to the given IANA timezone and return an ISO 8601 string with UTC offset.

    Returns None when tz_name is unknown or the conversion fails.
    """
    try:
        return dt.astimezone(ZoneInfo(tz_name)).isoformat()
    except (ZoneInfoNotFoundError, KeyError):
        return None
