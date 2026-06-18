from __future__ import annotations

# pylint R0801 (duplicate-code) may be reported here as a false positive:
# short common patterns (e.g. "if not rows: return None") in unrelated files
# can trigger the similarity checker against this module.
import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_FULL_DATE: re.Pattern[str] = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})$")  # 1985-04-12 or 19850412
_YEARLESS_DATE: re.Pattern[str] = re.compile(r"^--(\d{2})-?(\d{2})$")     # --0412 or --04-12


def to_utc(dt: datetime | date) -> datetime:
    """Convert a datetime or date to a UTC-aware datetime.

    Naive datetimes are assumed UTC. Date-only values are converted to midnight UTC.
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def today_iso() -> str:
    """Return today's UTC date as an ISO 8601 string (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).date().isoformat()


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


def combine_in_tz_to_utc(day: date, wall_time: time, tz: ZoneInfo) -> datetime:
    """Combine a date and a wall-clock time interpreted in ``tz``, returning a UTC-aware datetime."""
    return datetime.combine(day, wall_time, tzinfo=tz).astimezone(timezone.utc)


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


def normalize_partial_date(value: str) -> str | None:
    """Normalise a date that may omit the year (vCard reduced accuracy, RFC 6350 4.3.1).

    Accepts full ("1985-04-12" / "19850412") and year-less ("--0412" / "--04-12") forms; returns the
    canonical extended string ("YYYY-MM-DD" or "--MM-DD"), or None on a text / partial-other form.
    """
    text: str = value.strip()
    full: re.Match[str] | None = _FULL_DATE.match(text)
    if full is not None:
        year, month, day = full.groups()
        try:
            date(int(year), int(month), int(day))  # reject an impossible calendar date
        except ValueError:
            return None
        return f"{year}-{month}-{day}"
    yearless: re.Match[str] | None = _YEARLESS_DATE.match(text)
    if yearless is not None:
        month, day = yearless.groups()
        if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
            return None
        return f"--{month}-{day}"
    return None


def partial_date_to_basic(canonical: str) -> str:
    """Render a canonical date (normalize_partial_date output) in basic form: YYYYMMDD or --MMDD."""
    if canonical.startswith("--"):
        return "--" + canonical[2:].replace("-", "")
    return canonical.replace("-", "")
