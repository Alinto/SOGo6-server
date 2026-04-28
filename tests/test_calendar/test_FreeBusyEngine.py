"""Tests for FreeBusyEngine."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.module.calendar.freebusy.FreeBusyEngine import FreeBusyEngine, FreeBusyPrefs
from app.module.calendar.model.CalEvent import CalEvent
from app.utils.calendar.DateTimeUtils import resolve_tz
from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.model.enums.ShowAs import ShowAs

_UTC = timezone.utc


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def _make_event(date_start, date_end, show_as=ShowAs.BUSY, status=EventStatus.CONFIRMED, visibility=EventVisibility.PUBLIC):
    """Build a minimal CalEvent stub for FreeBusyEngine testing."""
    return CalEvent(
        uid="test@example.com",
        title="Test",
        date_start=date_start,
        date_end=date_end,
        show_as=show_as,
        status=status,
        visibility=visibility,
    )


_ENGINE = FreeBusyEngine()
_PREFS_NO_OOH = FreeBusyPrefs(busy_off_hours=False)
_PREFS_OOH = FreeBusyPrefs(busy_off_hours=True, workday_start="09:00", workday_end="17:00")


# ========== Event classification ==========

def test_busy_event_included():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10))
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert len(result) == 1
    assert result[0].fb_type == FreeBusyType.BUSY


def test_tentative_event_maps_to_tentative():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), show_as=ShowAs.TENTATIVE)
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result[0].fb_type == FreeBusyType.TENTATIVE


def test_out_of_office_maps_to_unavailable():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), show_as=ShowAs.OUT_OF_OFFICE)
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result[0].fb_type == FreeBusyType.UNAVAILABLE


def test_free_event_excluded():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), show_as=ShowAs.FREE)
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result == []


def test_cancelled_event_excluded():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), status=EventStatus.CANCELLED)
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result == []


# ========== Period clipping ==========

def test_period_clipped_to_query_range():
    # Event starts before query range and ends after
    event = _make_event(_dt(2026, 4, 22, 8), _dt(2026, 4, 22, 12))
    start = _dt(2026, 4, 22, 9)
    end = _dt(2026, 4, 22, 11)
    result = _ENGINE.compute([event], start, end, _PREFS_NO_OOH)
    assert result[0].date_start == start
    assert result[0].date_end == end


# ========== Merge ==========

def test_overlapping_periods_merged():
    e1 = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 11))
    e2 = _make_event(_dt(2026, 4, 22, 10), _dt(2026, 4, 22, 12))
    result = _ENGINE.compute([e1, e2], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert len(result) == 1
    assert result[0].date_start == _dt(2026, 4, 22, 9)
    assert result[0].date_end == _dt(2026, 4, 22, 12)


def test_event_ending_at_query_start_excluded():
    # Event 14:00-15:00, query 15:00-16:00: DB returns the event (date_end >= start),
    # but after clipping the period is [15:00, 15:00] — zero duration, must be dropped.
    event = _make_event(_dt(2026, 4, 22, 14), _dt(2026, 4, 22, 15))
    result = _ENGINE.compute(
        [event],
        _dt(2026, 4, 22, 15),
        _dt(2026, 4, 22, 16),
        _PREFS_NO_OOH,
    )
    assert result == []


def test_adjacent_periods_not_merged():
    # Event A ends at 16:00, event B starts at 16:00 — they share an instant but do not overlap.
    # The person is free starting at 16:00; the two periods must remain separate.
    e1 = _make_event(_dt(2026, 4, 22, 15), _dt(2026, 4, 22, 16))
    e2 = _make_event(_dt(2026, 4, 22, 16), _dt(2026, 4, 22, 17))
    result = _ENGINE.compute([e1, e2], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert len(result) == 2
    assert result[0].date_end == _dt(2026, 4, 22, 16)
    assert result[1].date_start == _dt(2026, 4, 22, 16)


def test_non_overlapping_periods_kept_separate():
    e1 = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10))
    e2 = _make_event(_dt(2026, 4, 22, 14), _dt(2026, 4, 22, 15))
    result = _ENGINE.compute([e1, e2], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert len(result) == 2


def test_different_types_not_merged():
    e1 = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 11))
    e2 = _make_event(_dt(2026, 4, 22, 10), _dt(2026, 4, 22, 12), show_as=ShowAs.TENTATIVE)
    result = _ENGINE.compute([e1, e2], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert len(result) == 2


# ========== busy_off_hours: weekends ==========

def test_off_hours_weekend_is_unavailable():
    # 2026-04-25 is a Saturday
    result = _ENGINE.compute(
        [],
        _dt(2026, 4, 25, 0),
        _dt(2026, 4, 25, 23, 59),
        _PREFS_OOH,
    )
    assert any(p.fb_type == FreeBusyType.UNAVAILABLE for p in result)


def test_off_hours_no_unavailable_without_flag():
    # Saturday — but busy_off_hours is False
    result = _ENGINE.compute(
        [],
        _dt(2026, 4, 25, 0),
        _dt(2026, 4, 25, 23, 59),
        _PREFS_NO_OOH,
    )
    assert result == []


# ========== busy_off_hours: before/after work hours ==========

def test_off_hours_before_work_is_unavailable():
    # 2026-04-22 is a Wednesday — check 00:00-09:00 is UNAVAILABLE
    result = _ENGINE.compute(
        [],
        _dt(2026, 4, 22, 0),
        _dt(2026, 4, 22, 23, 59),
        _PREFS_OOH,
    )
    unavailable = [p for p in result if p.fb_type == FreeBusyType.UNAVAILABLE]
    assert any(p.date_start == _dt(2026, 4, 22, 0) for p in unavailable)


def test_off_hours_after_work_is_unavailable():
    result = _ENGINE.compute(
        [],
        _dt(2026, 4, 22, 0),
        _dt(2026, 4, 22, 23, 59),
        _PREFS_OOH,
    )
    unavailable = [p for p in result if p.fb_type == FreeBusyType.UNAVAILABLE]
    assert any(p.date_end.hour >= 17 for p in unavailable)


# ========== All-day events ==========

def test_allday_event_is_busy_when_query_overlaps():
    """An all-day event stored with exclusive date_end (next day) must appear as busy
    for any query that falls within the event day."""
    event = _make_event(
        _dt(2026, 4, 28, 0),
        _dt(2026, 4, 29, 0),  # exclusive end — correct RFC 5545 storage
        show_as=ShowAs.BUSY,
    )
    event.all_day = True
    result = _ENGINE.compute([event], _dt(2026, 4, 28, 13, 58), _dt(2026, 4, 29, 13, 58), _PREFS_NO_OOH)
    assert len(result) == 1
    assert result[0].fb_type == FreeBusyType.BUSY


def test_allday_zero_duration_not_busy():
    """An all-day event stored with date_end == date_start (zero duration, malformed)
    must NOT appear as busy — this confirms the server-side normalization is necessary."""
    event = _make_event(
        _dt(2026, 4, 28, 0),
        _dt(2026, 4, 28, 0),  # zero duration — wrong, but tests the engine behaviour
    )
    event.all_day = True
    result = _ENGINE.compute([event], _dt(2026, 4, 28, 13, 58), _dt(2026, 4, 29, 13, 58), _PREFS_NO_OOH)
    assert result == []


# ========== _parse_time ==========

def test_parse_time():
    assert FreeBusyEngine._parse_time("09:30") == time(9, 30)  # pylint: disable=protected-access


# ========== _resolve_tz ==========

def test_resolve_tz_valid():
    assert resolve_tz("Europe/Paris") == ZoneInfo("Europe/Paris")


def test_resolve_tz_fallback():
    assert resolve_tz("Invalid/Timezone") == ZoneInfo("UTC")


# ========== Result ordering ==========

def test_result_sorted_by_date_start():
    e1 = _make_event(_dt(2026, 4, 22, 14), _dt(2026, 4, 22, 15))
    e2 = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10))
    result = _ENGINE.compute([e1, e2], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result[0].date_start < result[1].date_start


# ========== Event visibility and title ==========

def test_public_title():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), visibility=EventVisibility.PUBLIC)
    event.title = "Public meeting"
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result[0].title == "Public meeting"


def test_private_title():
    event = _make_event(_dt(2026, 4, 22, 9), _dt(2026, 4, 22, 10), visibility=EventVisibility.PRIVATE)
    event.title = "Secret"
    result = _ENGINE.compute([event], _dt(2026, 4, 22), _dt(2026, 4, 22, 23), _PREFS_NO_OOH)
    assert result[0].title is None
