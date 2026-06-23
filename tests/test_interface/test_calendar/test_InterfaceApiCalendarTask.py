"""Unit tests for InterfaceApiCalendarCalendar - task (VTODO) CRUD methods."""
# pylint: disable=missing-function-docstring
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.module.calendar.model.CalendarUser import CalendarUser

import pytest

from app.interface.calendar.InterfaceApiCalendarCalendar import InterfaceApiCalendarCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.module.calendar.serializer.CalEventsSerializerDict import CalEventsSerializerDict
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_task(**kwargs):
    defaults = {
        "uid": "task@example.com",
        "title": "My Task",
        "date_start": _dt(2026, 3, 1),
        "date_end": _dt(2026, 3, 2),
        "key": "task-key",
        "component_type": ComponentType.TASK,
    }
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_interface(module=None):
    inter = object.__new__(InterfaceApiCalendarCalendar)
    inter.user = MagicMock()
    inter.user.uid = "user@example.com"
    inter.module = module if module is not None else MagicMock()
    # Owner resolvers short-circuit to owner == acting user (no shared calendars today).
    inter.module.get_calendar.return_value.calendar.user_uid = inter.user.uid
    inter.module.get_event_calendar.return_value.user_uid = inter.user.uid
    inter._event_serializer = CalEventSerializerDict()
    inter._events_serializer = CalEventsSerializerDict()
    inter._event_deserializer = CalEventDeserializerDict()
    return inter


# ========== get_tasks ==========

def test_get_tasks_success():
    tasks = [_make_task(key="t1"), _make_task(key="t2", uid="t2@example.com")]
    module = MagicMock()
    module.get_tasks.return_value = tasks
    inter = _build_interface(module)
    response, _ = inter.get_tasks("cal-key", {})
    assert response["error_code"] == "S000000"
    assert response["data"]["total_count"] == 2


def test_get_tasks_calendar_not_found():
    module = MagicMock()
    module.get_tasks.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_tasks("missing", {})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_FOUND.c


def test_get_tasks_unexpected_error_propagates():
    module = MagicMock()
    module.get_tasks.side_effect = RuntimeError("boom")
    inter = _build_interface(module)
    with pytest.raises(RuntimeError):
        inter.get_tasks("cal-key", {})


def test_get_tasks_passes_default_dates_when_no_args():
    module = MagicMock()
    module.get_tasks.return_value = []
    inter = _build_interface(module)
    inter.get_tasks("cal-key", {})
    module.get_tasks.assert_called_once()
    call_args = module.get_tasks.call_args
    assert call_args[0][4] == "cal-key"
    assert call_args[0][1] is not None
    assert call_args[0][2] is not None


# ========== create_task ==========

def test_create_task_success():
    task = _make_task()
    module = MagicMock()
    module.create_task.return_value = task
    inter = _build_interface(module)
    body = {"title": "My Task"}
    response, _ = inter.create_task("cal-key", body)
    assert response["error_code"] == "S000000"
    module.create_task.assert_called_once()


def test_create_task_returns_task_data():
    task = _make_task(title="Buy milk")
    module = MagicMock()
    module.create_task.return_value = task
    inter = _build_interface(module)
    response, _ = inter.create_task("cal-key", {"title": "Buy milk"})
    assert response["data"]["title"] == "Buy milk"
    assert response["data"]["component_type"] == "task"


def test_create_task_due_mapped_to_date_end():
    due_iso = "2026-05-01T00:00:00+00:00"
    task = _make_task(date_end=datetime(2026, 5, 1, tzinfo=_UTC))
    module = MagicMock()
    module.create_task.return_value = task
    inter = _build_interface(module)
    inter.create_task("cal-key", {"title": "T", "date_due": due_iso})
    call_args = module.create_task.call_args
    created_event = call_args[0][2]
    assert created_event.date_end is not None


def test_create_task_request_exception_returns_error():
    module = MagicMock()
    module.create_task.side_effect = RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
    inter = _build_interface(module)
    response, _ = inter.create_task("cal-key", {"title": "T"})
    assert response["error_code"] == err.ERROR_CALENDAR_NOT_SUPPORTED.c


def test_create_task_parse_error_returns_json_parse_failed():
    module = MagicMock()
    inter = _build_interface(module)
    response, _ = inter.create_task("cal-key", {"title": "T", "date_start": "not-a-date"})
    assert response["error_code"] == err.ERROR_CALENDAR_JSON_PARSE_FAILED.c


def test_create_task_unexpected_error_propagates():
    module = MagicMock()
    module.create_task.side_effect = RuntimeError("unexpected")
    inter = _build_interface(module)
    with pytest.raises(RuntimeError):
        inter.create_task("cal-key", {"title": "T"})


# ========== get_task ==========

def test_get_task_success():
    task = _make_task()
    module = MagicMock()
    module.get_task.return_value = task
    inter = _build_interface(module)
    response, _ = inter.get_task("task-key")
    assert response["error_code"] == "S000000"
    assert response["data"]["uid"] == "task@example.com"


def test_get_task_not_found():
    module = MagicMock()
    module.get_task.side_effect = RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.get_task("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_TASK_NOT_FOUND.c


def test_get_task_serializes_due():
    task = _make_task(date_end=_dt(2026, 6, 15, 12))
    module = MagicMock()
    module.get_task.return_value = task
    inter = _build_interface(module)
    response, _ = inter.get_task("task-key")
    assert "2026-06-15" in response["data"]["date_due"]
    assert "date_end" not in response["data"]


def test_get_task_without_due_returns_null():
    # A task with no due date has date_end=None, surfaced as due=null.
    task = _make_task(date_end=None)
    module = MagicMock()
    module.get_task.return_value = task
    inter = _build_interface(module)
    response, _ = inter.get_task("task-key")
    assert response["data"]["date_due"] is None


# ========== patch_task ==========

def test_patch_task_applies_updates():
    existing = _make_task(title="Old")
    updated = _make_task(title="Updated")
    module = MagicMock()
    module.get_task.return_value = existing
    module.update_task.return_value = updated
    inter = _build_interface(module)
    response, _ = inter.patch_task("task-key", {"title": "Updated"})
    assert response["error_code"] == "S000000"
    assert response["data"]["title"] == "Updated"


def test_patch_task_due_mapped_to_date_end():
    existing = _make_task()
    module = MagicMock()
    module.get_task.return_value = existing
    module.update_task.return_value = existing
    inter = _build_interface(module)
    inter.patch_task("task-key", {"date_due": "2026-07-01T00:00:00+00:00"})
    call_args = module.update_task.call_args
    task_update = call_args[0][2]
    assert task_update.date_end == datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def test_patch_task_not_found_returns_error():
    module = MagicMock()
    module.get_task.side_effect = RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.patch_task("missing-key", {"title": "X"})
    assert response["error_code"] == err.ERROR_CALENDAR_TASK_NOT_FOUND.c


def test_patch_task_parse_error_returns_json_parse_failed():
    existing = _make_task()
    module = MagicMock()
    module.get_task.return_value = existing
    inter = _build_interface(module)
    response, _ = inter.patch_task("task-key", {"recurrence_exceptions": ["not-a-date"]})
    assert response["error_code"] == err.ERROR_CALENDAR_JSON_PARSE_FAILED.c


def test_patch_task_unexpected_error_propagates():
    existing = _make_task()
    module = MagicMock()
    module.get_task.return_value = existing
    module.update_task.side_effect = RuntimeError("db gone")
    inter = _build_interface(module)
    with pytest.raises(RuntimeError):
        inter.patch_task("task-key", {"title": "X"})


# ========== delete_task ==========

def test_delete_task_success():
    module = MagicMock()
    inter = _build_interface(module)
    response, _ = inter.delete_task("task-key")
    assert response["error_code"] == "S000000"
    assert response["data"] is None
    module.delete_task.assert_called_once_with(CalendarUser(user=inter.user, owner=inter.user), "task-key")


def test_delete_task_not_found_returns_error():
    module = MagicMock()
    module.delete_task.side_effect = RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
    inter = _build_interface(module)
    response, _ = inter.delete_task("missing-key")
    assert response["error_code"] == err.ERROR_CALENDAR_TASK_NOT_FOUND.c


def test_delete_task_unexpected_error_propagates():
    module = MagicMock()
    module.delete_task.side_effect = RuntimeError("boom")
    inter = _build_interface(module)
    with pytest.raises(RuntimeError):
        inter.delete_task("task-key")
