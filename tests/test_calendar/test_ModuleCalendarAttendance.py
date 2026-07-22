"""Unit tests for ModuleCalendar.set_attendance_status."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.module.calendar.model.CalendarUser import CalendarUser

import pytest

from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Meeting",
        date_start=_dt(2026, 6, 1, 9),
        date_end=_dt(2026, 6, 1, 10),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _organizer(email="organizer@example.com"):
    return CalOrganizer(email=email, name="Alice")


def _attendee(email="attendee@example.com", status=AttendeeStatus.NEEDS_ACTION):
    return CalAttendee(email=email, name="Bob", status=status)


def _fake_user(uid="attendee@example.com"):
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    return CalendarUser(user=user, owner=user)


class FakeAttendanceSource(CalendarSource):
    def __init__(self, calendar, events=None, writable=True):
        super().__init__(calendar)
        self._events = {e.key: e for e in (events or [])}
        self._writable = writable
        self.updated = []
        self.partstat_propagated = []

    def _fetch_events(self, start, end, search=None):
        return list(self._events.values())

    def is_writable(self):
        return self._writable

    def get_event(self, event_key):
        return self._events.get(event_key)

    def update_event(self, event):
        self._events[event.key] = event
        self.updated.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def propagate_partstat_to_copies(self, event, attendee_email, status):
        self.partstat_propagated.append((event.uid, attendee_email, status))

    def update_calendar(self, calendar):
        self._calendar = calendar


def _make_source(key="cal-key", events=None, writable=True):
    cal = CalCalendar(key=key, user_uid="attendee@example.com", name="Cal", ctag=0)
    return FakeAttendanceSource(cal, events=events, writable=writable)


def _build_module(sources: dict):
    module = object.__new__(ModuleCalendar)
    sources_mock = MagicMock()
    sources_mock.get_all.return_value = list(sources.values())
    sources_mock.get_default.return_value = None
    sources_mock.find_by_uid.return_value = None

    def _require_event(uid, event_key):
        for s in sources.values():
            ev = s.get_event(event_key)
            if ev is not None:
                return s, ev
        raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

    sources_mock.require_event.side_effect = _require_event
    module._sources = sources_mock
    module._imip = ImipProcessor(sources_mock)
    module._db = MagicMock()
    module._cache = MagicMock()
    module._acl = MagicMock()
    return module


# ========== Tests for set_attendance_status ==========

def test_attendance_accepted():
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    result = module.set_attendance_status(
        _fake_user("attendee@example.com"), "evt-key", AttendeeStatus.ACCEPTED, sequence=0,
    )

    assert result.attendees[0].status == AttendeeStatus.ACCEPTED
    assert len(source.updated) == 1


def test_attendance_declined():
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    result = module.set_attendance_status(
        _fake_user("attendee@example.com"), "evt-key", AttendeeStatus.DECLINED, sequence=0,
    )

    assert result.attendees[0].status == AttendeeStatus.DECLINED


def test_attendance_tentative():
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    result = module.set_attendance_status(
        _fake_user("attendee@example.com"), "evt-key", AttendeeStatus.TENTATIVE, sequence=0,
    )

    assert result.attendees[0].status == AttendeeStatus.TENTATIVE


def test_attendance_user_not_attendee_is_rejected():
    """Answering for an event one was not invited to is reported, not silently accepted."""
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("other@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    with pytest.raises(RequestException) as exc_info:
        module.set_attendance_status(_fake_user("attendee@example.com"), "evt-key", AttendeeStatus.ACCEPTED, sequence=0)

    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_ATTENDEE
    assert event.attendees[0].status == AttendeeStatus.NEEDS_ACTION
    assert len(source.updated) == 0


def test_attendance_already_current_skips_write():
    """Re-sending the current status must not touch the DB - the ETag would move for nothing."""
    event = _make_event(
        key="evt-key", organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.ACCEPTED)],
    )
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    result = module.set_attendance_status(_fake_user(), "evt-key", AttendeeStatus.ACCEPTED, sequence=0)

    assert result.attendees[0].status == AttendeeStatus.ACCEPTED
    assert len(source.updated) == 0
    assert source.partstat_propagated == []


def test_attendance_on_obsolete_revision_is_rejected():
    """A caller reporting the revision it was shown is refused once the organizer has moved the slot."""
    event = _make_event(
        key="evt-key", sequence=3, organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.NEEDS_ACTION)],
    )
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    with pytest.raises(RequestException) as exc_info:
        module.set_attendance_status(_fake_user(), "evt-key", AttendeeStatus.ACCEPTED, sequence=2)

    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_REVISION_OBSOLETE
    assert event.attendees[0].status == AttendeeStatus.NEEDS_ACTION
    assert len(source.updated) == 0


def test_attendance_does_not_increment_sequence():
    """PARTSTAT update must not change SEQUENCE (RFC 5545 §3.8.7.4)."""
    event = _make_event(key="evt-key", sequence=3, organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    result = module.set_attendance_status(
        _fake_user("attendee@example.com"), "evt-key", AttendeeStatus.ACCEPTED, sequence=3,
    )

    assert result.sequence == 3


def test_attendance_propagates_partstat_to_copies():
    """After updating own status, propagate_partstat_to_copies must be called."""
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    module.set_attendance_status(_fake_user("attendee@example.com"), "evt-key", AttendeeStatus.ACCEPTED, sequence=0)

    assert len(source.partstat_propagated) == 1
    uid, email, status = source.partstat_propagated[0]
    assert uid == "evt@example.com"
    assert email == "attendee@example.com"
    assert status == AttendeeStatus.ACCEPTED


def test_attendance_bumps_ctag():
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee("attendee@example.com")])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    module.set_attendance_status(_fake_user("attendee@example.com"), "evt-key", AttendeeStatus.ACCEPTED, sequence=0)

    assert source.calendar.ctag == 1


def test_attendance_event_not_found_raises():
    source = _make_source(events=[])
    module = _build_module({"cal-key": source})

    with pytest.raises(RequestException) as exc_info:
        module.set_attendance_status(_fake_user(), "nonexistent", AttendeeStatus.ACCEPTED, sequence=0)
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_attendance_single_occurrence():
    """Declining a single occurrence creates a detached override and leaves master unchanged."""
    master = _make_event(
        key="evt-key", organizer=_organizer(),
        attendees=[_attendee("attendee@example.com")],
        recurrence_rule=CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, count=4),
    )
    source = _make_source(events=[master])

    # Simulate get_or_create_occurrence: create a detached copy for the target date
    target_dt = _dt(2026, 6, 8, 9)
    occurrence = _make_event(
        key="evt-key-occ-20260608", uid=master.uid,
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com")],
        date_start=target_dt, date_end=_dt(2026, 6, 8, 10),
        recurrence_id=target_dt,
    )
    source.get_or_create_occurrence = lambda m, rid: occurrence

    module = _build_module({"cal-key": source})
    result = module.set_attendance_status(
        _fake_user("attendee@example.com"), "evt-key", AttendeeStatus.DECLINED, sequence=0, recurrence_id=target_dt,
    )

    assert result.recurrence_id == target_dt
    assert result.attendees[0].status == AttendeeStatus.DECLINED
    # Master attendee status unchanged
    assert master.attendees[0].status == AttendeeStatus.NEEDS_ACTION


def test_attendance_acl_denied_raises():
    event = _make_event(key="evt-key", organizer=_organizer(), attendees=[_attendee()])
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    module._acl.check_permission.side_effect = RequestException(error=err.ERROR_CALENDAR_ACCESS_DENIED)

    with pytest.raises(RequestException) as exc_info:
        module.set_attendance_status(_fake_user(), "evt-key", AttendeeStatus.ACCEPTED, sequence=0)
    assert exc_info.value.error == err.ERROR_CALENDAR_ACCESS_DENIED
