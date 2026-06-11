"""Unit tests for CalEvent model."""
from datetime import datetime, timedelta, timezone

import pytest

from app.module.calendar.CalendarConst import MAX_EVENT_ALL_DAY_DURATION_HOURS, MAX_EVENT_DURATION_HOURS
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        date_start=_dt(2026, 6, 1, 9),
        date_end=_dt(2026, 6, 1, 10),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


# ========== validate ==========

def test_validate_ok():
    event = _make_event()
    event.validate()


def test_validate_exact_max_duration():
    event = _make_event(
        date_start=_dt(2026, 6, 1, 0),
        date_end=_dt(2026, 6, 1, 0) + timedelta(hours=MAX_EVENT_DURATION_HOURS),
    )
    event.validate()


def test_validate_exceeds_max_duration():
    event = _make_event(
        date_start=_dt(2026, 6, 1, 0),
        date_end=_dt(2026, 6, 1, 0) + timedelta(hours=MAX_EVENT_DURATION_HOURS, minutes=1),
    )
    with pytest.raises(RequestException):
        event.validate()


def test_validate_all_day_within_cap():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 5),
    )
    event.validate()


def test_validate_all_day_exact_max_duration():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_ALL_DAY_DURATION_HOURS),
    )
    event.validate()


def test_validate_all_day_exceeds_max_duration():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_ALL_DAY_DURATION_HOURS, minutes=1),
    )
    with pytest.raises(RequestException):
        event.validate()


def test_validate_all_day_exceeds_uses_all_day_cap_not_default():
    # Duration > MAX_EVENT_DURATION_HOURS but < MAX_EVENT_ALL_DAY_DURATION_HOURS:
    # passes only because the all_day branch applies a higher cap.
    assert MAX_EVENT_ALL_DAY_DURATION_HOURS > MAX_EVENT_DURATION_HOURS
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_DURATION_HOURS + 1),
    )
    event.validate()


def test_validate_no_dates():
    event = _make_event(date_start=None, date_end=None)
    event.validate()


# ========== is_organized_by ==========

def test_is_organized_by_matches():
    event = _make_event(organizer=CalOrganizer(email="bob@example.com"))
    assert event.is_organized_by("bob@example.com") is True
    assert event.is_organized_by("alice@example.com") is False


def test_is_organized_by_false_without_organizer():
    event = _make_event(organizer=None)
    assert event.is_organized_by("bob@example.com") is False
