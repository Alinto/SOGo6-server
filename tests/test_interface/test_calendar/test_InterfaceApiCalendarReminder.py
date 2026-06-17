"""Unit tests for InterfaceApiCalendarCalendar — get_reminders method."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.module.calendar.model.CalendarUser import CalendarUser

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.serializer.CalEventReminderSerializerDict import CalEventReminderSerializerDict
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def _build_interface(module=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "user@example.com"
    inter.module = module if module is not None else MagicMock()
    inter._reminder_serializer = CalEventReminderSerializerDict()
    return inter


def _make_reminder(**kwargs):
    defaults = dict(
        event_key="evt-key",
        title="Test",
        location="Room A",
        date_start=_dt(2026, 6, 1, 10),
        date_end=_dt(2026, 6, 1, 11),
        timezone="Europe/Paris",
        calendar_timezone="Europe/Paris",
        method=ReminderMethod.POPUP,
        minutes_before=15,
        trigger_at=_dt(2026, 6, 1, 9, 45),
    )
    defaults.update(kwargs)
    return CalEventReminder(**defaults)


# ========== get_reminders ==========

def test_get_reminders_success():
    module = MagicMock()
    module.get_reminders.return_value = [_make_reminder()]
    inter = _build_interface(module)
    response, _ = inter.get_reminders({})
    assert response["error_code"] == "S000000"
    assert response["data"]["total_count"] == 1
    r = response["data"]["reminders"][0]
    assert r["event_key"] == "evt-key"
    assert r["title"] == "Test"
    assert r["location"] == "Room A"
    assert r["method"] == "popup"
    assert r["minutes_before"] == 15
    assert "dates_with_tz" in r
    assert r["dates_with_tz"]["date_start_tz_event"] is not None


def test_get_reminders_empty():
    module = MagicMock()
    module.get_reminders.return_value = []
    inter = _build_interface(module)
    response, _ = inter.get_reminders({})
    assert response["error_code"] == "S000000"
    assert response["data"]["total_count"] == 0
    assert response["data"]["reminders"] == []


def test_get_reminders_passes_method_filter():
    module = MagicMock()
    module.get_reminders.return_value = []
    inter = _build_interface(module)
    inter.get_reminders({"method": "email"})
    call_kwargs = module.get_reminders.call_args[1]
    assert call_kwargs["method"].value == "email"


def test_get_reminders_passes_user():
    module = MagicMock()
    module.get_reminders.return_value = []
    inter = _build_interface(module)
    inter.get_reminders({})
    call_kwargs = module.get_reminders.call_args[1]
    assert call_kwargs["calendar_user"] == CalendarUser(user=inter.user, owner=inter.user)


def test_get_reminders_no_method_passes_none():
    module = MagicMock()
    module.get_reminders.return_value = []
    inter = _build_interface(module)
    inter.get_reminders({})
    call_kwargs = module.get_reminders.call_args[1]
    assert call_kwargs["method"] is None


def test_get_reminders_passes_lookahead():
    module = MagicMock()
    module.get_reminders.return_value = []
    inter = _build_interface(module)
    inter.get_reminders({"lookahead": 30})
    call_kwargs = module.get_reminders.call_args[1]
    assert call_kwargs["lookahead_minutes"] == 30


def test_get_reminders_request_exception():
    module = MagicMock()
    module.get_reminders.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_reminders({})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c


def test_get_reminders_invalid_method():
    module = MagicMock()
    inter = _build_interface(module)
    response, _ = inter.get_reminders({"method": "invalid_method"})
    assert response["error_code"] == err.ERROR_CALENDAR_JSON_PARSE_FAILED.c
