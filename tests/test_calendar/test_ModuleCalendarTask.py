"""Unit tests for ModuleCalendar task (VTODO) CRUD methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.CalendarConst import MAX_TASK_FETCH_DAYS
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_task(**kwargs):
    defaults = dict(
        uid="task@example.com",
        title="My Task",
        date_start=_dt(2026, 3, 1),
        date_end=_dt(9999, 12, 31),
        component_type=ComponentType.TASK,
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


class FakeTaskSource(CalendarSource):
    def __init__(self, calendar, tasks=None, writable=True):
        super().__init__(calendar)
        self._items = {t.key: t for t in (tasks or [])}
        self._writable = writable
        self.inserted = []
        self.updated = []
        self.deleted_uids = []
        self.calendar_updated = False

    def _fetch_events(self, start, end, search=None):
        return []

    def _fetch_tasks(self, start, end, search=None):
        return [t for t in self._items.values() if t.component_type == ComponentType.TASK]

    def is_writable(self):
        return self._writable

    def get_event(self, event_key):
        return self._items.get(event_key)

    def insert_event(self, event):
        event.db_id = 1
        event.key = event.key or "new-task-key"
        self._items[event.key] = event
        self.inserted.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1
        return event

    def update_event(self, event):
        self._items[event.key] = event
        self.updated.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def delete_event(self, uid):
        self.deleted_uids.append(uid)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def update_calendar(self, calendar):
        self.calendar_updated = True
        self._calendar = calendar


def _fake_user(uid="user@example.com"):
    user = MagicMock()
    user.uid = uid
    return user


def _build_module(sources: dict):
    module = object.__new__(ModuleCalendar)
    sources_mock = MagicMock()
    sources_mock.get_all.return_value = list(sources.values())
    sources_mock.get_by_key.side_effect = lambda uid, key: sources.get(key)
    sources_mock.get.side_effect = lambda cal: sources.get(cal.key)
    sources_mock.get_default.return_value = None
    sources_mock.find_by_uid.return_value = None

    def _get_tasks(uid, start, end, search, calendar_key=None):
        if calendar_key is not None:
            source = sources.get(calendar_key)
            if source is None:
                raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
            return source.get_tasks(start, end, search)
        return [t for s in sources.values() for t in s.get_tasks(start, end, search)]

    sources_mock.get_tasks.side_effect = _get_tasks
    module._sources = sources_mock
    module._imip = ImipProcessor(sources_mock)
    module._db = MagicMock()
    return module


def _make_source(key="cal-key", tasks=None, writable=True):
    cal = CalCalendar(key=key, user_uid="user@example.com", name="My Cal", ctag=0)
    return FakeTaskSource(cal, tasks=tasks, writable=writable)


# ========== create_task ==========

def test_create_task_sets_component_type():
    source = _make_source()
    module = _build_module({"cal-key": source})
    task = _make_task()
    result = module.create_task(_fake_user(), "cal-key", task)
    assert result.component_type == ComponentType.TASK


def test_create_task_bumps_ctag():
    source = _make_source()
    module = _build_module({"cal-key": source})
    module.create_task(_fake_user(), "cal-key", _make_task())
    assert source.calendar.ctag == 1


def test_create_task_raises_on_read_only():
    source = _make_source(writable=False)
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.create_task(_fake_user(), "cal-key", _make_task())
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


def test_create_task_raises_on_unknown_calendar():
    module = _build_module({})
    with pytest.raises(RequestException) as exc_info:
        module.create_task(_fake_user(), "nonexistent", _make_task())
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_create_task_generates_uid_when_absent():
    source = _make_source()
    module = _build_module({"cal-key": source})
    task = _make_task(uid="")
    module.create_task(_fake_user(), "cal-key", task)
    assert task.uid != ""


def test_create_task_preserves_uid_when_present():
    source = _make_source()
    module = _build_module({"cal-key": source})
    task = _make_task(uid="existing-uid@example.com")
    module.create_task(_fake_user(), "cal-key", task)
    assert task.uid == "existing-uid@example.com"


def test_create_task_sets_calendar_key():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    task = _make_task()
    result = module.create_task(_fake_user(), "cal-key", task)
    assert result.calendar_key == source.calendar.key


# ========== get_task ==========

def test_get_task_found():
    task = _make_task(key="task-key")
    source = _make_source(tasks=[task])
    module = _build_module({"cal-key": source})
    result = module.get_task(_fake_user(), "task-key")
    assert result.uid == "task@example.com"


def test_get_task_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.get_task(_fake_user(), "missing-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_get_task_rejects_event_key():
    """get_task must reject items with component_type != TASK."""
    event = CalEvent(
        uid="evt@example.com", title="Event", key="evt-key",
        date_start=datetime(2026, 3, 1, tzinfo=_UTC),
        date_end=datetime(2026, 3, 1, 1, tzinfo=_UTC),
        component_type=ComponentType.EVENT,
    )
    source = _make_source()
    source._items["evt-key"] = event  # pylint: disable=protected-access
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.get_task(_fake_user(), "evt-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_TASK_NOT_FOUND


# ========== update_task ==========

def test_update_task_applies_patch():
    task = _make_task(key="task-key", title="Old")
    source = _make_source(tasks=[task])
    module = _build_module({"cal-key": source})
    update = _make_task(title="New")
    result = module.update_task(_fake_user(), "task-key", update)
    assert result.title == "New"


def test_update_task_bumps_ctag():
    task = _make_task(key="task-key")
    source = _make_source(tasks=[task])
    module = _build_module({"cal-key": source})
    update = _make_task(title="X")
    module.update_task(_fake_user(), "task-key", update)
    assert source.calendar.ctag == 1


def test_update_task_rejects_event_key():
    event = CalEvent(
        uid="evt@example.com", title="Evt", key="evt-key",
        date_start=datetime(2026, 3, 1, tzinfo=_UTC),
        date_end=datetime(2026, 3, 1, 1, tzinfo=_UTC),
        component_type=ComponentType.EVENT,
    )
    source = _make_source()
    source._items["evt-key"] = event  # pylint: disable=protected-access
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_task(_fake_user(), "evt-key", {"title": "X"})
    assert exc_info.value.error == err.ERROR_CALENDAR_TASK_NOT_FOUND


# ========== delete_task ==========

def test_delete_task_calls_source_delete():
    task = _make_task(key="task-key", uid="del-task@example.com")
    source = _make_source(tasks=[task])
    module = _build_module({"cal-key": source})
    module.delete_task(_fake_user(), "task-key")
    assert "del-task@example.com" in source.deleted_uids


def test_delete_task_bumps_ctag():
    task = _make_task(key="task-key")
    source = _make_source(tasks=[task])
    module = _build_module({"cal-key": source})
    module.delete_task(_fake_user(), "task-key")
    assert source.calendar.ctag == 1


def test_delete_task_rejects_event_key():
    event = CalEvent(
        uid="evt@example.com", title="Evt", key="evt-key",
        date_start=datetime(2026, 3, 1, tzinfo=_UTC),
        date_end=datetime(2026, 3, 1, 1, tzinfo=_UTC),
        component_type=ComponentType.EVENT,
    )
    source = _make_source()
    source._items["evt-key"] = event  # pylint: disable=protected-access
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.delete_task(_fake_user(), "evt-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_TASK_NOT_FOUND


# ========== get_tasks ==========

def test_get_tasks_returns_tasks():
    task1 = _make_task(key="t1", uid="t1@example.com")
    task2 = _make_task(key="t2", uid="t2@example.com")
    source = _make_source(tasks=[task1, task2])
    module = _build_module({"cal-key": source})
    results = module.get_tasks(_fake_user(), None, None, None, "cal-key")
    assert len(results) == 2


def test_get_tasks_unknown_calendar_raises():
    module = _build_module({})
    with pytest.raises(RequestException) as exc_info:
        module.get_tasks(_fake_user(), None, None, None, "nonexistent")
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_get_tasks_no_key_merges_all_calendars():
    task1 = _make_task(key="t1", uid="t1@example.com")
    task2 = _make_task(key="t2", uid="t2@example.com")
    source_a = _make_source("cal-a", tasks=[task1])
    source_b = _make_source("cal-b", tasks=[task2])
    module = _build_module({"cal-a": source_a, "cal-b": source_b})
    results = module.get_tasks(_fake_user(), None, None, None)
    assert len(results) == 2
    keys = {t.key for t in results}
    assert keys == {"t1", "t2"}


def test_get_tasks_no_key_empty_when_no_calendars():
    module = _build_module({})
    assert module.get_tasks(_fake_user(), None, None, None) == []


def test_get_tasks_date_range_too_large_raises():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = datetime(2026, 1, 1, tzinfo=_UTC)
    end = datetime(2027, 3, 1, tzinfo=_UTC)
    assert (end - start).days > MAX_TASK_FETCH_DAYS
    with pytest.raises(RequestException) as exc_info:
        module.get_tasks(_fake_user(), start, end, None, "cal-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE


def test_get_tasks_search_bypasses_date_range_limit():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = datetime(2026, 1, 1, tzinfo=_UTC)
    end = datetime(2028, 1, 1, tzinfo=_UTC)
    assert (end - start).days > MAX_TASK_FETCH_DAYS
    results = module.get_tasks(_fake_user(), start, end, "meeting", "cal-key")
    assert results is not None
