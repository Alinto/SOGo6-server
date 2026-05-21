"""Unit tests for InterfaceApiCalendarCalendar — calendar CRUD timezone defaulting."""
from unittest.mock import MagicMock

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarSerializerDict import CalendarSerializerDict


def _build_interface(user_tz="Europe/Paris"):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "alice@example.com"
    inter.user.mail = "alice@example.com"
    inter.module = MagicMock()
    # Return the calendar passed in so we can assert on what was built.
    inter.module.create_calendar.side_effect = lambda user, cal: cal
    inter._calendar_serializer = CalendarSerializerDict()
    inter._user_module = MagicMock()
    inter._user_module.get_partial_user_preferences.return_value = {"USER_GENERAL": {"SOGO_U_TIMEZONE": user_tz}}
    return inter


def _created_calendar(inter) -> CalCalendar:
    return inter.module.create_calendar.call_args.args[1]


def test_create_calendar_defaults_to_user_timezone():
    inter = _build_interface(user_tz="Europe/Paris")
    inter.create_calendar({"name": "Work"})
    assert _created_calendar(inter).timezone == "Europe/Paris"


def test_create_calendar_keeps_explicit_timezone():
    inter = _build_interface(user_tz="Europe/Paris")
    inter.create_calendar({"name": "Work", "timezone": "America/New_York"})
    assert _created_calendar(inter).timezone == "America/New_York"


def test_create_calendar_empty_timezone_falls_back_to_user():
    inter = _build_interface(user_tz="Asia/Tokyo")
    inter.create_calendar({"name": "Work", "timezone": ""})
    assert _created_calendar(inter).timezone == "Asia/Tokyo"
