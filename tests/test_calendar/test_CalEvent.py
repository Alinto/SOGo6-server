"""Unit tests for CalEvent model."""
from datetime import datetime, timedelta, timezone

import pytest

from app.module.calendar.CalendarConst import MAX_EVENT_DURATION_HOURS
from app.module.calendar.model.CalEvent import CalEvent
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


def test_validate_all_day_exempt():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 5),
    )
    event.validate()


def test_validate_no_dates():
    event = _make_event(date_start=None, date_end=None)
    event.validate()
