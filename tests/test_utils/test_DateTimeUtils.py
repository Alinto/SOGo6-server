"""Unit tests for app.utils.datetime.DateTimeUtils."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.utils.datetime.DateTimeUtils import (
    add_months,
    anchor_to_utc,
    combine_in_tz_to_utc,
    normalize_partial_date,
    partial_date_to_basic,
)

_UTC = timezone.utc


def test_normalize_partial_date_full():
    assert normalize_partial_date("1985-04-12") == "1985-04-12"
    assert normalize_partial_date("19850412") == "1985-04-12"  # basic -> canonical extended
    assert normalize_partial_date("  1985-04-12 ") == "1985-04-12"


def test_normalize_partial_date_yearless():
    assert normalize_partial_date("--0412") == "--04-12"
    assert normalize_partial_date("--04-12") == "--04-12"


def test_normalize_partial_date_rejects_invalid_and_text():
    assert normalize_partial_date("1985-13-40") is None  # impossible calendar date
    assert normalize_partial_date("circa 1800") is None  # text form
    assert normalize_partial_date("1985") is None        # year only, not modelled
    assert normalize_partial_date("--13-01") is None     # month out of range


def test_partial_date_to_basic():
    assert partial_date_to_basic("1985-04-12") == "19850412"
    assert partial_date_to_basic("--04-12") == "--0412"


def test_anchor_naive_with_default_tz():
    naive = datetime(2026, 6, 1, 10, 0, 0)
    # 10:00 in Paris (+02:00 in June) = 08:00 UTC
    assert anchor_to_utc(naive, "Europe/Paris") == datetime(2026, 6, 1, 8, 0, 0, tzinfo=_UTC)


def test_anchor_aware_ignores_default_tz():
    aware = datetime(2026, 6, 1, 10, 0, 0, tzinfo=_UTC)
    assert anchor_to_utc(aware, "America/New_York") == aware


def test_anchor_naive_without_default_tz_assumes_utc():
    naive = datetime(2026, 6, 1, 10, 0, 0)
    assert anchor_to_utc(naive, None) == datetime(2026, 6, 1, 10, 0, 0, tzinfo=_UTC)


def test_anchor_aware_non_utc_converts():
    aware_paris = datetime(2026, 6, 1, 10, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
    assert anchor_to_utc(aware_paris, None) == datetime(2026, 6, 1, 8, 0, 0, tzinfo=_UTC)


def test_anchor_unknown_default_tz_falls_back_to_utc():
    naive = datetime(2026, 6, 1, 10, 0, 0)
    # resolve_tz returns UTC for unknown zones -> naive stays at the same wall-clock in UTC
    assert anchor_to_utc(naive, "Mars/Olympus") == datetime(2026, 6, 1, 10, 0, 0, tzinfo=_UTC)


def test_combine_in_tz_to_utc_applies_offset():
    # 09:00 wall-clock in Paris (+02:00 in June) = 07:00 UTC
    result = combine_in_tz_to_utc(date(2026, 6, 1), time(9, 0, 0), ZoneInfo("Europe/Paris"))
    assert result == datetime(2026, 6, 1, 7, 0, 0, tzinfo=_UTC)


def test_combine_in_tz_to_utc_with_utc_zone():
    result = combine_in_tz_to_utc(date(2026, 6, 1), time(23, 59, 59), ZoneInfo("UTC"))
    assert result == datetime(2026, 6, 1, 23, 59, 59, tzinfo=_UTC)


def test_add_months_forward_and_back():
    assert add_months(datetime(2026, 6, 15, 9, tzinfo=_UTC), 9) == datetime(2027, 3, 15, 9, tzinfo=_UTC)
    assert add_months(datetime(2026, 6, 15, 9, tzinfo=_UTC), -3) == datetime(2026, 3, 15, 9, tzinfo=_UTC)


def test_add_months_clamps_to_last_day():
    # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year), not an invalid Feb 31.
    assert add_months(datetime(2026, 1, 31, tzinfo=_UTC), 1) == datetime(2026, 2, 28, tzinfo=_UTC)
