"""Unit tests for ModuleCalendar event CRUD methods."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.CalendarConst import MAX_EVENT_FETCH_DAYS
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction
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
        self.deleted_occurrence_keys = []
        self.calendar_updated = False

    def _fetch_events(self, start, end, search=None):
        return list(self._events.values())

    def is_writable(self):
        return self._writable

    def get_event(self, event_key):
        return self._events.get(event_key)

    def insert_event(self, event):
        event.db_id = "generated-id"
        event.key = event.key or "new-key"
        self._events[event.key] = event
        self.inserted.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1
        return event

    def realign_detached_occurrences(self, uid, old_start, new_start):
        self.realigned = {"uid": uid, "old_start": old_start, "new_start": new_start}
        return []

    def update_event(self, event):
        self._events[event.key] = event
        self.updated.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def delete_event(self, uid):
        self.deleted_uids.append(uid)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def delete_detached_occurrence(self, occurrence):
        self.deleted_occurrence_keys.append(occurrence.key)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def update_calendar(self, calendar):
        self.calendar_updated = True
        self._calendar = calendar


def _fake_user(uid="user@example.com"):
    user = MagicMock()
    user.uid = uid
    return user


def _build_module(sources: dict):
    """Return a ModuleCalendar with injected sources and mocked infrastructure."""
    module = object.__new__(ModuleCalendar)
    sources_mock = MagicMock()
    sources_mock.get_all.return_value = list(sources.values())
    sources_mock.get_by_key.side_effect = lambda uid, key: sources.get(key)
    sources_mock.get.side_effect = lambda cal: sources.get(cal.key)
    sources_mock.get_default.return_value = None
    sources_mock.find_by_uid.return_value = None

    def _get_events(uid, start, end, search, calendar_key=None):
        if calendar_key is not None:
            source = sources.get(calendar_key)
            if source is None:
                raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
            return source.get_events(start, end, search)
        return [e for s in sources.values() for e in s.get_events(start, end, search)]

    sources_mock.get_events.side_effect = _get_events
    module._sources = sources_mock
    module._imip = ImipProcessor(sources_mock)
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
    result = module.get_event(_fake_user(), "evt-key")
    assert result.uid == "evt@example.com"


def test_get_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.get_event(_fake_user(), "missing-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_get_event_searches_all_sources():
    event = _make_event(key="evt-key")
    source1 = _make_source("cal-1")
    source2 = _make_source("cal-2", events=[event])
    module = _build_module({"cal-1": source1, "cal-2": source2})
    result = module.get_event(_fake_user(), "evt-key")
    assert result.uid == "evt@example.com"


# ========== create_event ==========

def test_create_event_sets_calendar_key():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event()
    result = module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.calendar_key == source.calendar.key


def test_create_event_generates_uid_when_absent():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event(uid="")
    module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert event.uid != ""


def test_create_event_preserves_uid_when_present():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event(uid="existing-uid@example.com")
    module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert event.uid == "existing-uid@example.com"


def test_create_event_bumps_ctag():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    event = _make_event()
    module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert source.calendar.ctag == 1


def test_create_event_raises_on_read_only_source():
    source = _make_source("cal-key", writable=False)
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.create_event(_fake_user(), "cal-key", _make_event(), CalOrganizer(email="user@example.com"))
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


def test_create_event_raises_on_unknown_calendar():
    module = _build_module({})
    with pytest.raises(RequestException) as exc_info:
        module.create_event(_fake_user(), "nonexistent", _make_event(), CalOrganizer(email="user@example.com"))
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_FOUND


# ========== update_event ==========

def _merge(event, **kwargs):
    """Simulate deserialize_with_update: copy event and apply kwargs."""
    import dataclasses as _dc
    return _dc.replace(event, **kwargs)


def test_update_event_applies_patch():
    event = _make_event(key="evt-key", title="Old title")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event(_fake_user(), "evt-key", _merge(event, title="New title"), CalOrganizer(email="user@example.com"))
    assert result.title == "New title"


def test_update_event_ignores_unknown_fields():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event(_fake_user(), "evt-key", _merge(event), CalOrganizer(email="user@example.com"))
    assert result.uid == "evt@example.com"


def test_update_event_bumps_ctag():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.update_event(_fake_user(), "evt-key", _merge(event, title="Updated"), CalOrganizer(email="user@example.com"))
    assert source.calendar.ctag == 1


def test_update_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_event(_fake_user(), "missing-key", _make_event(), CalOrganizer(email="user@example.com"))
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_update_event_read_only_raises():
    event = _make_event(key="evt-key")
    source = _make_source(writable=False, events=[event])
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_event(_fake_user(), "evt-key", _merge(event), CalOrganizer(email="user@example.com"))
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


def test_update_event_attendee_cannot_modify():
    """An attendee (not the organizer) must not be able to modify event content."""
    organizer = CalOrganizer(email="organizer@example.com")
    event = _make_event(key="evt-key", organizer=organizer)
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.update_event(_fake_user("attendee@example.com"), "evt-key", _merge(event, title="Hacked"), CalOrganizer(email="attendee@example.com"))
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_ORGANIZER


# ========== update_event — detached occurrence shift ==========

def test_update_event_realigns_detached_when_start_changes():
    """When 'All events' moves date_start, detached occurrences must be realigned."""
    event = _make_event(key="evt-key", date_start=_dt(2026, 4, 27, 10), date_end=_dt(2026, 4, 27, 11))
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    update = _merge(event, date_start=_dt(2026, 4, 27, 12), date_end=_dt(2026, 4, 27, 13))
    module.update_event(_fake_user(), "evt-key", update, CalOrganizer(email="user@example.com"))
    assert hasattr(source, "realigned")
    assert source.realigned["uid"] == "evt@example.com"
    assert source.realigned["old_start"] == _dt(2026, 4, 27, 10)
    assert source.realigned["new_start"] == _dt(2026, 4, 27, 12)


def test_update_event_no_realign_when_start_unchanged():
    """When date_start stays the same, no realign should occur."""
    event = _make_event(key="evt-key", date_start=_dt(2026, 4, 27, 10), date_end=_dt(2026, 4, 27, 11))
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    update = _merge(event, title="Updated")
    module.update_event(_fake_user(), "evt-key", update, CalOrganizer(email="user@example.com"))
    assert not hasattr(source, "realigned")


def test_update_detached_occurrence_propagates_to_attendee_copies():
    """Editing a detached occurrence must propagate to attendee copies (not to their masters)."""
    organizer = CalOrganizer(email="user@example.com")
    detached = _make_event(
        key="occ-key", uid="series@example.com",
        recurrence_id=_dt(2026, 4, 30, 10),
        recurrence_rule=None,
        organizer=organizer,
    )
    source = _make_source(events=[detached])
    module = _build_module({"cal-key": source})
    update = _merge(detached, title="Modified Occurrence")
    module.update_event(_fake_user("user@example.com"), "occ-key", update, CalOrganizer(email="user@example.com"))
    assert source.updated[-1].title == "Modified Occurrence"


# ========== delete_event ==========

def test_delete_event_calls_source_delete():
    event = _make_event(key="evt-key", uid="to-delete@example.com")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event(_fake_user(), "evt-key")
    assert "to-delete@example.com" in source.deleted_uids


def test_delete_event_bumps_ctag():
    event = _make_event(key="evt-key")
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event(_fake_user(), "evt-key")
    assert source.calendar.ctag == 1


def test_delete_event_not_found_raises():
    source = _make_source()
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.delete_event(_fake_user(), "missing-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_delete_event_read_only_raises():
    event = _make_event(key="evt-key")
    source = _make_source(writable=False, events=[event])
    module = _build_module({"cal-key": source})
    with pytest.raises(RequestException) as exc_info:
        module.delete_event(_fake_user(), "evt-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_SUPPORTED


# ========== delete_event — recurrence handling ==========

def test_delete_event_occurrence_routes_to_delete_detached():
    """delete_event on a detached occurrence (recurrence_id set) must call
    delete_detached_occurrence, not delete_event(uid), to avoid deleting the master."""
    rid = datetime(2026, 3, 9, 9, 0, tzinfo=_UTC)
    occurrence = _make_event(key="occ-key", uid="master@example.com", recurrence_id=rid)
    source = _make_source(events=[occurrence])
    module = _build_module({"cal-key": source})
    module.delete_event(_fake_user(), "occ-key")
    assert "occ-key" in source.deleted_occurrence_keys
    assert "master@example.com" not in source.deleted_uids


def test_get_events_date_range_too_large_raises():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = datetime(2026, 1, 1, tzinfo=_UTC)
    end = datetime(2026, 3, 1, tzinfo=_UTC)
    assert (end - start).days > MAX_EVENT_FETCH_DAYS
    with pytest.raises(RequestException) as exc_info:
        module.get_events(_fake_user(), start, end, None, "cal-key")
    assert exc_info.value.error == err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE


def test_get_events_search_bypasses_date_range_limit():
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = datetime(2026, 1, 1, tzinfo=_UTC)
    end = datetime(2027, 1, 1, tzinfo=_UTC)
    assert (end - start).days > MAX_EVENT_FETCH_DAYS
    results = module.get_events(_fake_user(), start, end, "meeting", "cal-key")
    assert results is not None


def test_get_events_no_key_merges_all_calendars():
    evt1 = _make_event(key="e1", uid="e1@example.com", calendar_key="cal-a")
    evt2 = _make_event(key="e2", uid="e2@example.com", calendar_key="cal-b")
    source_a = _make_source("cal-a", events=[evt1])
    source_b = _make_source("cal-b", events=[evt2])
    module = _build_module({"cal-a": source_a, "cal-b": source_b})
    results = module.get_events(_fake_user(), None, None, None)
    assert len(results) == 2
    keys = {e.key for e in results}
    assert keys == {"e1", "e2"}


def test_get_events_no_key_unknown_calendar_not_raised():
    module = _build_module({})
    results = module.get_events(_fake_user(), None, None, None)
    assert results == []


# ========== clean ==========

def test_clean_by_calendar_key():
    module = _build_module({})
    module._db.delete_row_in_table.return_value = 3
    count = module.clean(calendar_key="cal-key")
    # 3 events purged + 3 reminders purged
    assert count == 6
    assert module._db.delete_row_in_table.call_count == 2


def test_clean_by_user_uid_aggregates_across_calendars():
    source1 = _make_source("cal-1")
    source2 = _make_source("cal-2")
    module = _build_module({"cal-1": source1, "cal-2": source2})
    module._db.delete_row_in_table.return_value = 2
    count = module.clean(user_uid="user@example.com")
    # 2 events per calendar (2*2=4) + 2 reminders purged = 6
    assert count == 6
    assert module._db.delete_row_in_table.call_count == 3


def test_clean_no_args_returns_zero():
    module = _build_module({})
    assert module.clean() == 0


# ========== delete_event — organizer vs attendee ==========

def test_delete_event_organizer_deletes_own_copy():
    """When the organizer deletes, their own copy is deleted via delete_event(uid)."""
    organizer = CalOrganizer(email="user@example.com")
    attendee = CalAttendee(email="other@example.com")
    event = _make_event(key="evt-key", uid="org-event@example.com", organizer=organizer, attendees=[attendee])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event(_fake_user("user@example.com"), "evt-key")
    assert "org-event@example.com" in source.deleted_uids


def test_delete_event_attendee_deletes_own_copy():
    """When an attendee deletes, only their own copy is deleted."""
    organizer = CalOrganizer(email="organizer@example.com")
    event = _make_event(key="evt-key", uid="evt@example.com", organizer=organizer)
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module.delete_event(_fake_user("user@example.com"), "evt-key")
    assert "evt@example.com" in source.deleted_uids
    assert "organizer:evt@example.com" not in source.deleted_uids


# ========== update_event — sequence ==========

def test_update_event_increments_sequence():
    """update_event must always increment SEQUENCE (RFC 5545 §3.8.7.4)."""
    event = _make_event(key="evt-key", sequence=2)
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event(_fake_user(), "evt-key", _merge(event, title="Updated"), CalOrganizer(email="user@example.com"))
    assert result.sequence == 3


# ========== create_event — auto organizer ==========

def test_create_event_auto_sets_organizer_when_attendees_present():
    """When creating an event with attendees but no organizer, the organizer must be set
    to the creating user (RFC 5545 §3.8.4.3 — ORGANIZER is required when ATTENDEE is present)."""
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    attendee = CalAttendee(email="guest@example.com")
    event = _make_event(attendees=[attendee])
    result = module.create_event(_fake_user("user@example.com"), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.organizer is not None
    assert result.organizer.email == "user@example.com"


def test_create_event_preserves_explicit_organizer():
    """When an organizer is already set, create_event must not overwrite it."""
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    organizer = CalOrganizer(email="explicit@example.com")
    attendee = CalAttendee(email="guest@example.com")
    event = _make_event(organizer=organizer, attendees=[attendee])
    result = module.create_event(_fake_user("user@example.com"), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.organizer.email == "explicit@example.com"


# ========== all-day normalization (RFC 5545 §3.6.1) ==========

def test_create_allday_normalizes_zero_duration():
    """create_event must set date_end = date_start + 1 day when all_day=True and date_end <= date_start."""
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = _dt(2026, 4, 28)
    event = _make_event(all_day=True, date_start=start, date_end=start)
    result = module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.date_end == _dt(2026, 4, 29)


def test_update_allday_normalizes_zero_duration():
    """update_event must normalize date_end when the patch produces date_end <= date_start."""
    start = _dt(2026, 4, 28)
    event = _make_event(key="evt-key", all_day=True, date_start=start, date_end=_dt(2026, 4, 29))
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    result = module.update_event(_fake_user(), "evt-key", _merge(event, all_day=True, date_start=start, date_end=start), CalOrganizer(email="user@example.com"))
    assert result.date_end == _dt(2026, 4, 29)


def test_create_allday_already_correct_not_changed():
    """create_event must not alter date_end when it is already strictly after date_start."""
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = _dt(2026, 4, 28)
    end = _dt(2026, 4, 30)
    event = _make_event(all_day=True, date_start=start, date_end=end)
    result = module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.date_end == end


def test_non_allday_event_date_end_unchanged():
    """_normalize_all_day must not touch regular (non-all-day) events."""
    source = _make_source("cal-key")
    module = _build_module({"cal-key": source})
    start = _dt(2026, 4, 28, 9)
    end = _dt(2026, 4, 28, 9)
    event = _make_event(all_day=False, date_start=start, date_end=end)
    result = module.create_event(_fake_user(), "cal-key", event, CalOrganizer(email="user@example.com"))
    assert result.date_end == end
