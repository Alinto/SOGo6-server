"""Unit tests for ModuleCalendar export and import."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalSyncResult import CalSyncResult
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


class FakeSource(CalendarSource):
    def __init__(self, calendar, events=None, writable=True):
        super().__init__(calendar)
        self._events = list(events or [])
        self._writable = writable

    def _fetch_events(self, start, end, search=None):
        return list(self._events)

    def is_writable(self):
        return self._writable


def _fake_user(uid="alice@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return user


def _build_module(source):
    module = object.__new__(ModuleCalendar)
    module._db = MagicMock()
    module._cache = MagicMock()
    module._acl = MagicMock()
    sources_mock = MagicMock()
    sources_mock.get_by_key.return_value = source
    module._sources = sources_mock
    module._imip = ImipProcessor(sources_mock)
    return module


def _make_source(events=None, writable=True):
    cal = CalCalendar(key="cal-key", user_uid="alice@example.com", name="My Cal", ctag=0, timezone="UTC")
    return FakeSource(cal, events=events, writable=writable)


# ========== serialize_to_ics ==========

def test_export_returns_vcalendar_with_events():
    event = _make_event(uid="event-1", key="evt-1")
    source = _make_source(events=[event])
    module = _build_module(source)
    result = module.serialize_to_ics(_fake_user(), "cal-key")
    assert "BEGIN:VCALENDAR" in result
    assert "END:VCALENDAR" in result
    assert "event-1" in result


def test_export_empty_calendar_still_returns_vcalendar():
    source = _make_source(events=[])
    module = _build_module(source)
    result = module.serialize_to_ics(_fake_user(), "cal-key")
    assert "BEGIN:VCALENDAR" in result
    assert "END:VCALENDAR" in result


def test_export_unknown_calendar_raises():
    module = _build_module(None)
    module._sources.get_by_key.return_value = None
    with pytest.raises(RequestException) as exc:
        module.serialize_to_ics(_fake_user(), "missing-key")
    assert exc.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_export_preserves_recurrence_rule_unexpanded():
    from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
    from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency

    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, count=5)
    event = _make_event(uid="recurring", key="rec-1", recurrence_rule=rule)
    source = _make_source(events=[event])
    module = _build_module(source)
    result = module.serialize_to_ics(_fake_user(), "cal-key")
    assert "RRULE:" in result
    assert "FREQ=WEEKLY" in result


# ========== apply_import (sync, worker-side) ==========

_MIN_ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\nUID:imported-1\r\nDTSTAMP:20260301T090000Z\r\n"
    "DTSTART:20260301T090000Z\r\nDTEND:20260301T100000Z\r\nSUMMARY:Imported\r\n"
    "ORGANIZER:mailto:bob@example.com\r\nATTENDEE:mailto:charlie@example.com\r\n"
    "END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_import_forwards_owner_email_for_rewrite_by_default():
    source = _make_source()
    module = _build_module(source)
    with patch("app.module.calendar.ModuleCalendar.SyncEngine") as engine_class:
        engine = MagicMock()
        engine.apply_ics.return_value = CalSyncResult(inserted=1, total=1)
        engine_class.return_value = engine
        module.apply_import(_fake_user("alice@example.com"), "cal-key", _MIN_ICS)
    kwargs = engine.apply_ics.call_args.kwargs
    assert kwargs["rewrite_owner_email"] == "alice@example.com"
    assert kwargs["delete_missing"] is False
    # Floating events are anchored to the destination calendar timezone.
    assert kwargs["default_timezone"] == "UTC"


def test_import_omits_owner_email_when_ownership_toggle_off():
    source = _make_source()
    module = _build_module(source)
    with patch("app.module.calendar.ModuleCalendar.IMPORT_REWRITES_OWNERSHIP", False), \
         patch("app.module.calendar.ModuleCalendar.SyncEngine") as engine_class:
        engine = MagicMock()
        engine.apply_ics.return_value = CalSyncResult(inserted=1, total=1)
        engine_class.return_value = engine
        module.apply_import(_fake_user(), "cal-key", _MIN_ICS)
    assert engine.apply_ics.call_args.kwargs["rewrite_owner_email"] is None


def test_import_rejects_readonly_calendar():
    source = _make_source(writable=False)
    module = _build_module(source)
    with pytest.raises(RequestException) as exc:
        module.apply_import(_fake_user(), "cal-key", _MIN_ICS)
    assert exc.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


def test_import_rejects_oversized_payload():
    source = _make_source()
    module = _build_module(source)
    with patch("app.module.calendar.ModuleCalendar.MAX_IMPORT_ICS_BYTES", 10):
        with pytest.raises(RequestException) as exc:
            module.apply_import(_fake_user(), "cal-key", _MIN_ICS)
        assert exc.value.error == err.ERROR_CALENDAR_IMPORT_TOO_LARGE


def test_import_returns_sync_result():
    source = _make_source()
    module = _build_module(source)
    with patch("app.module.calendar.ModuleCalendar.SyncEngine") as engine_class:
        engine = MagicMock()
        engine.apply_ics.return_value = CalSyncResult(inserted=3, updated=1, total=4)
        engine_class.return_value = engine
        result = module.apply_import(_fake_user(), "cal-key", _MIN_ICS)
    assert result.inserted == 3
    assert result.updated == 1
    assert result.deleted == 0


# ========== import_calendar (async, API-side) ==========

def test_async_import_offloads_blob_and_enqueues_job():
    source = _make_source()
    module = _build_module(source)
    module._agent = MagicMock()
    module._agent.enqueue.return_value = "job-77"
    ref = MagicMock()
    module._agent.get_large_store.return_value.save.return_value = ref
    job_id = module.import_calendar(_fake_user("alice@example.com"), "cal-key", _MIN_ICS.encode("utf-8"))
    assert job_id == "job-77"
    module._agent.get_large_store.return_value.save.assert_called_once_with(_MIN_ICS.encode("utf-8"), "text/calendar")
    request = module._agent.enqueue.call_args.args[0]
    assert request.source_ref is ref
    assert request.calendar_key == "cal-key"
    assert module._agent.enqueue.call_args.kwargs["user_uid"] == "alice@example.com"


def test_async_import_drops_blob_when_enqueue_fails():
    source = _make_source()
    module = _build_module(source)
    module._agent = MagicMock()
    module._agent.enqueue.side_effect = RuntimeError("queue down")
    ref = MagicMock()
    module._agent.get_large_store.return_value.save.return_value = ref
    with pytest.raises(RuntimeError):
        module.import_calendar(_fake_user(), "cal-key", _MIN_ICS.encode("utf-8"))
    # The offloaded blob is dropped - nothing dangling.
    module._agent.get_large_store.return_value.delete.assert_called_once_with(ref)


def test_async_import_rejects_oversized_payload_before_offload():
    source = _make_source()
    module = _build_module(source)
    module._agent = MagicMock()
    with patch("app.module.calendar.ModuleCalendar.MAX_IMPORT_ICS_BYTES", 10):
        with pytest.raises(RequestException) as exc:
            module.import_calendar(_fake_user(), "cal-key", _MIN_ICS.encode("utf-8"))
    assert exc.value.error == err.ERROR_CALENDAR_IMPORT_TOO_LARGE
    module._agent.get_large_store.return_value.save.assert_not_called()
    module._agent.enqueue.assert_not_called()


def test_async_import_rejects_readonly_calendar():
    source = _make_source(writable=False)
    module = _build_module(source)
    module._agent = MagicMock()
    with pytest.raises(RequestException) as exc:
        module.import_calendar(_fake_user(), "cal-key", _MIN_ICS.encode("utf-8"))
    assert exc.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED
    module._agent.get_large_store.return_value.save.assert_not_called()
