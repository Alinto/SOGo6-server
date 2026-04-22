"""Unit tests for InterfaceApiCalendarCalendar — event CRUD methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        date_start=_dt(2026, 3, 1, 9),
        date_end=_dt(2026, 3, 1, 10),
        key="evt-key",
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_interface(module=None):
    from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson
    from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson
    from app.module.calendar.serializer.CalendarEventsSerializerJson import CalendarEventsSerializerJson
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "user@example.com"
    inter.module = module if module is not None else MagicMock()
    inter._event_serializer = CalendarEventSerializerJson()
    inter._event_deserializer = CalendarEventDeserializerJson()
    inter._events_serializer = CalendarEventsSerializerJson()
    return inter


# ========== create_event ==========

def test_create_event_success():
    event = _make_event()
    module = MagicMock()
    module.create_event.return_value = event
    inter = _build_interface(module)
    body = {
        "uid": "new@example.com",
        "title": "New event",
        "date_start": "2026-03-01T09:00:00.000Z",
        "date_end": "2026-03-01T10:00:00.000Z",
    }
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == "S000000"
    module.create_event.assert_called_once()


def test_create_event_returns_event_data():
    event = _make_event(title="Meeting")
    module = MagicMock()
    module.create_event.return_value = event
    inter = _build_interface(module)
    body = {
        "title": "Meeting",
        "date_start": "2026-03-01T09:00:00.000Z",
        "date_end": "2026-03-01T10:00:00.000Z",
    }
    response, _ = inter.create_event("cal-key", body)
    assert response["data"]["title"] == "Meeting"


def test_create_event_request_exception_returns_error():
    module = MagicMock()
    module.create_event.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    body = {"title": "T", "date_start": "2026-03-01T09:00:00.000Z", "date_end": "2026-03-01T10:00:00.000Z"}
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c


def test_create_event_unexpected_exception_returns_unknown_error():
    module = MagicMock()
    module.create_event.side_effect = RuntimeError("unexpected")
    inter = _build_interface(module)
    body = {"title": "T", "date_start": "2026-03-01T09:00:00.000Z", "date_end": "2026-03-01T10:00:00.000Z"}
    response, _ = inter.create_event("cal-key", body)
    assert response["error_code"] == err.ERROR_UNKOWN.c


# ========== get_event ==========

def test_get_event_success():
    event = _make_event()
    module = MagicMock()
    module.get_event.return_value = event
    inter = _build_interface(module)
    response, _ = inter.get_event("evt-key")
    assert response["error_code"] == "S000000"
    assert response["data"]["uid"] == "evt@example.com"


def test_get_event_not_found():
    module = MagicMock()
    module.get_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_event("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


# ========== patch_event ==========

def test_patch_event_applies_updates():
    event = _make_event(title="Updated title")
    module = MagicMock()
    module.update_event.return_value = event
    inter = _build_interface(module)
    response, _ = inter.patch_event("evt-key", {"title": "Updated title"})
    assert response["error_code"] == "S000000"
    assert response["data"]["title"] == "Updated title"


def test_patch_event_not_found_returns_error():
    module = MagicMock()
    module.update_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.patch_event("missing-key", {"title": "X"})
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


# ========== delete_event ==========

def test_delete_event_success():
    module = MagicMock()
    inter = _build_interface(module)
    response, _ = inter.delete_event("evt-key")
    assert response["error_code"] == "S000000"
    assert response["data"] is None
    module.delete_event.assert_called_once_with("evt-key")


def test_delete_event_not_found_returns_error():
    module = MagicMock()
    module.delete_event.side_effect = RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.delete_event("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_EVENT_NOT_FOUND.c


def test_delete_event_unexpected_error_returns_unknown():
    module = MagicMock()
    module.delete_event.side_effect = RuntimeError("boom")
    inter = _build_interface(module)
    response, _ = inter.delete_event("evt-key")
    assert response["error_code"] == err.ERROR_UNKOWN.c
