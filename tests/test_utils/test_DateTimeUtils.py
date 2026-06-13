"""Unit tests for app.utils.datetime.DateTimeUtils."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.utils.datetime.DateTimeUtils import anchor_to_utc, combine_in_tz_to_utc

_UTC = timezone.utc


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
