from __future__ import annotations

# pylint R0801 (duplicate-code) may be reported here as a false positive:
# short common patterns (e.g. "if not rows: return None") in unrelated files
# can trigger the similarity checker against this module.
import re
from calendar import monthrange
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


def add_months(dt: datetime, months: int) -> datetime:
    """Return dt shifted by the given number of months, clamping to the last day of the target month."""
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def apply_tz(dt: datetime, tz_name: str) -> str | None:
    """Convert dt to the given IANA timezone and return an ISO 8601 string with UTC offset.

    Returns None when tz_name is unknown or the conversion fails.
    """
    try:
        return dt.astimezone(ZoneInfo(tz_name)).isoformat()
    except (ZoneInfoNotFoundError, KeyError):
        return None


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string into a tz-aware UTC datetime, or None when absent.

    Naive values are assumed UTC; tz-aware values are converted to UTC.
    """
    if not value:
        return None
    return to_utc(datetime.fromisoformat(value))


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


def parse_vacation_datetime(dt_str: str | None, default_tz: str = "UTC", tz_converter=None) -> tuple[str | None, str | None, str | None]:
    """Parse a vacation datetime string with optional timezone.
    
    Supports formats:
    - Date only: "2026-06-15" → returns (date, None, default_tz)
    - DateTime: "2026-06-15T14:30:00" → returns (date, time, default_tz)
    - DateTime with +HH:MM: "2026-06-15T14:30:00+0100" → returns (date, time, extracted_tz)
    - DateTime with :Zone: "2026-06-15T14:30:00:Europe/Paris" → returns (date, time, "Europe/Paris")
    - DateTime with Z: "2026-06-15T14:30:00Z" → returns (date, time, "UTC")
    
    Returns the timezone already converted using the provided tz_converter function.
    When default_tz is an IANA name (e.g., "Europe/Paris"), it's converted once here.
    
    :param dt_str: DateTime string to parse
    :param default_tz: Default timezone if none specified in the string (can be IANA name or offset)
    :param tz_converter: Optional function to convert timezone strings (e.g., to Sieve format).
                        If None, returns the timezone string as-is.
    :return: Tuple of (date_str, time_str, timezone_str_converted) - time_str is None for date-only
    """
    # Use identity function if no converter provided
    if tz_converter is None:
        tz_converter = lambda tz, dt=None: tz
    
    if not dt_str or not isinstance(dt_str, str):
        normalized_tz = tz_converter(default_tz)
        return None, None, normalized_tz
    
    dt_str = dt_str.strip()
    if not dt_str:
        normalized_tz = tz_converter(default_tz)
        return None, None, normalized_tz
    
    # Check if it's date-only (YYYY-MM-DD)
    if len(dt_str) == 10 and dt_str.count("-") == 2:
        try:
            datetime.strptime(dt_str, "%Y-%m-%d")
            # Normalize timezone, using the date for DST correctness
            normalized_tz = tz_converter(default_tz, dt_str)
            return dt_str, None, normalized_tz
        except ValueError:
            normalized_tz = tz_converter(default_tz)
            return None, None, normalized_tz
    
    # Try to parse datetime with timezone
    if "T" not in dt_str:
        normalized_tz = tz_converter(default_tz)
        return None, None, normalized_tz
    
    date_part, time_part = dt_str.split("T", 1)
    
    # Validate date part
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        normalized_tz = tz_converter(default_tz)
        return None, None, normalized_tz
    
    extracted_tz = default_tz
    time_only = None
    
    # Check for timezone info in the time part
    if time_part.endswith("Z"):
        # UTC marker
        time_only = time_part[:-1]
        extracted_tz = "UTC"
    elif "+" in time_part:
        # Format with +HH:MM or +HHMM
        idx = time_part.rfind("+")
        time_only = time_part[:idx]
        tz_offset = time_part[idx:]  # Keep as "+HH:MM" or "+HHMM"
        extracted_tz = tz_offset
    elif time_part.count("-") > 0 and time_part.rfind("-") > 7:
        # Format with -HH:MM (negative UTC offset)
        # Find the last dash; only treat as timezone if it appears after the minimum time length
        idx = time_part.rfind("-")
        if idx > 0:
            time_only = time_part[:idx]
            tz_offset = time_part[idx:]
            extracted_tz = tz_offset
        else:
            time_only = time_part
    elif ":" in time_part and time_part.count(":") > 2:
        # Check for :Zone format (e.g., "14:30:00:Europe/Paris")
        # If more than 2 colons (HH:MM:SS = 2), there might be a timezone
        parts = time_part.rsplit(":", 1)
        time_only = parts[0]
        tz_candidate = parts[1]
        # Validate it looks like a timezone (contains / or other valid indicators)
        if "/" in tz_candidate or tz_candidate.startswith("UTC") or tz_candidate.startswith("GMT"):
            extracted_tz = tz_candidate
        else:
            # Not a timezone, just regular time
            time_only = time_part
    else:
        # No timezone info in time part - use default_tz
        time_only = time_part
    
    # Return parsed components with timezone converted using provided converter
    # Pass date_part to converter so it can account for DST
    if time_only and len(time_only.split(":")) >= 2:
        normalized_tz = tz_converter(extracted_tz, date_part)
        return date_part, time_only, normalized_tz
    
    # No valid time found
    normalized_tz = tz_converter(extracted_tz, date_part)
    return date_part, None, normalized_tz
