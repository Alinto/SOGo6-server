"""Unit tests for ModuleCalendar event CRUD methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.source.CalendarSource import CalendarSource
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
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


class FakeCalendarSource(CalendarSource):
    def __init__(self, calendar, events=None, writable=True):
        super().__init__(calendar)
        self._events = {e.key: e for e in (events or [])}
        self._writable = writable
        self.inserted = []
        self.updated = []
        self.deleted_uids = []
        self.calendar_updated = False

    def _fetch_events(self, start, end, search=None):
        return list(self._events.values())

    def is_writable(self):
        return self._writable

    def get_event(self, event_key):
        return self._events.get(event_key)

    def insert_event(self, event):
        event.id = "generated-id"
        event.key = event.key or "new-key"
        self._events[event.key] = event
        self.inserted.append(event)
        return event

    def update_event(self, event):
        self._events[event.key] = event
        self.updated.append(event)

    def delete_event(self, uid):
        self.deleted_uids.append(uid)

    def update_calendar(self, calendar):
        self.calendar_updated = True
        self._calendar = calendar


def _build_module(sources: dict):
    """Return a ModuleCalendar with injected sources and mocked infrastructure."""
    from app.module.calendar.ModuleCalendar import ModuleCalendar
    module = object.__new__(ModuleCalendar)
    module.user = MagicMock()
    module.user.uid = "user@example.com"
    sources_mock = MagicMock()
    sources_mock.get_all.return_value = list(sources.values())
    sources_mock.get_by_key.side_effect = lambda uid, key: sources.get(key)
    sources_mock.get.side_effect = lambda cal: sources.get(cal.key)
    module._sources = sources_mock
    module._db = MagicMock()
    return module


def _make_source(key="cal-key", events=None, writable=True):
    cal = CalCalendar(key=key, user_uid="user@example.com", name="My Cal", ctag=0)
    return FakeCalendarSource(cal, events=events, writable=writable)


# ========== get_event ==========

def test_get_event_found():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.get_event("evt-key")
    assert result.uid == "evt@example.com"


def test_get_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.get_event("missing-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_get_event_searches_all_sources():
    event = _make_event(key="evt-key")
    source1 = _make_source("cal-1")
    source2 = _make_source("cal-2", events=[event])
    module = _build_module({"cal-1": source1, "cal-2": source2})
    result = module.get_event("evt-key")
    assert result.uid == "evt@example.com"


# ========== create_event ==========

def test_create_event_sets_calendar_id():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event()
    result = module.create_event("cal-key", event)
    assert result.calendar_id == source.calendar.id


def test_create_event_generates_uid_when_absent():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event(uid="")
    module.create_event("cal-key", event)
    assert event.uid != ""


def test_create_event_preserves_uid_when_present():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event(uid="existing-uid@example.com")
    module.create_event("cal-key", event)
    assert event.uid == "existing-uid@example.com"


def test_create_event_bumps_ctag():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event()
    module.create_event("cal-key", event)
    assert source.calendar.ctag == 1
    assert source.calendar_updated is True


def test_create_event_raises_on_read_only_source():
    source = _make_source("cal-key", writable=False)
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.create_event("cal-key", _make_event())
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


def test_create_event_raises_on_unknown_calendar():
    module = _build_module({})
    with pytest.raises(RequestException) as exc_info:
        module.create_event("nonexistent", _make_event())
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_FOUND


# ========== update_event ==========

def test_update_event_applies_patch():
    event = _make_event(key="evt-key", title="Old title")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event("evt-key", {"title": "New title"})
    assert result.title == "New title"


def test_update_event_ignores_unknown_fields():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event("evt-key", {"nonexistent_field": "value"})
    assert result.uid == "evt@example.com"


def test_update_event_bumps_ctag():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.update_event("evt-key", {"title": "Updated"})
    assert source.calendar.ctag == 1


def test_update_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_event("missing-key", {"title": "X"})
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_update_event_read_only_raises():
    event = _make_event(key="evt-key")
    source = _make_source(writable=False, events=[event])
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_event("evt-key", {"title": "X"})
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


# ========== delete_event ==========

def test_delete_event_calls_source_delete():
    event = _make_event(key="evt-key", uid="to-delete@example.com")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event("evt-key")
    assert "to-delete@example.com" in source.deleted_uids


def test_delete_event_bumps_ctag():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event("evt-key")
    assert source.calendar.ctag == 1


def test_delete_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.delete_event("missing-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_delete_event_read_only_raises():
    event = _make_event(key="evt-key")
    source = _make_source(writable=False, events=[event])
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.delete_event("evt-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED
