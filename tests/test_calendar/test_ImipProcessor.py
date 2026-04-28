"""Unit tests for ImipProcessor (REQUEST, REPLY, CANCEL flows)."""
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock

import pytest

from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.imip.ImipProcessor import ImipProcessor
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc
_serializer = CalendarEventSerializerIcal()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=_UTC)


def _organizer(email="organizer@example.com"):
    return CalOrganizer(email=email, name="Alice")


def _attendee(email="attendee@example.com", status=AttendeeStatus.NEEDS_ACTION):
    return CalAttendee(email=email, name="Bob", status=status)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Meeting",
        date_start=_dt(2026, 6, 1, 9),
        date_end=_dt(2026, 6, 1, 10),
        sequence=1,
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_imip_bytes(event: CalEvent, method: str) -> bytes:
    ical = _serializer.build_imip(event, method)
    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg.attach(MIMEText(ical, "calendar", "utf-8"))
    return msg.as_bytes()


def _fake_user(uid="organizer@example.com"):
    user = MagicMock()
    user.uid = uid
    return user


class FakeImipSource(CalendarSource):
    """Minimal fake source for iMIP tests. Looks up events by UID."""

    def __init__(self, calendar, events=None, writable=True):
        super().__init__(calendar)
        self._by_uid = {e.uid: e for e in (events or [])}
        self._by_key = {e.key: e for e in (events or []) if e.key}
        self._writable = writable
        self.updated = []
        self.deleted_uids = []
        self.inserted = []

    def _fetch_events(self, start, end, search=None):
        return list(self._by_uid.values())

    def is_writable(self):
        return self._writable

    def get_event(self, event_key):
        return self._by_key.get(event_key)

    def get_master_event_by_uid(self, uid):
        return self._by_uid.get(uid)

    def insert_event(self, event):
        event.key = event.key or "new-key"
        self._by_uid[event.uid] = event
        self.inserted.append(event)
        return event

    def update_event(self, event, propagate=False):
        self._by_uid[event.uid] = event
        self.updated.append(event)
        self._calendar.ctag = (self._calendar.ctag or 0) + 1

    def delete_event(self, uid):
        self.deleted_uids.append(uid)

    def update_calendar(self, calendar):
        self._calendar = calendar


def _build_module(sources: dict, default_key: str = "cal-key"):
    module = object.__new__(ModuleCalendar)
    mock_sources = MagicMock()
    mock_sources.get_all.return_value = list(sources.values())
    mock_sources.get_by_key.side_effect = lambda uid, key: sources.get(key)
    mock_sources.get_default.return_value = sources.get(default_key)

    def _find_by_uid(user_uid, uid):
        for source in sources.values():
            event = source.get_master_event_by_uid(uid)
            if event is not None:
                return source, event
        return None

    mock_sources.find_by_uid.side_effect = _find_by_uid
    module._sources = mock_sources
    module._imip = ImipProcessor(mock_sources)
    module._db = MagicMock()
    return module


def _make_source(key="cal-key", events=None, writable=True, is_default=True):
    cal = CalCalendar(key=key, user_uid="organizer@example.com", name="Cal", ctag=0, is_default=is_default)
    return FakeImipSource(cal, events=events, writable=writable)


# ========== Tests for process_imip_reply ==========

def test_reply_updates_partstat():
    org_event = _make_event(
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.NEEDS_ACTION)],
    )
    source = _make_source(events=[org_event])
    module = _build_module({"cal-key": source})

    # Build a REPLY where attendee accepts
    reply_event = _make_event(
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.ACCEPTED)],
    )
    raw = _build_imip_bytes(reply_event, "REPLY")

    result = module.process_imip_reply(_fake_user(), raw, "attendee@example.com")

    assert result.attendees[0].status == AttendeeStatus.ACCEPTED
    assert len(source.updated) == 1


def test_reply_attendee_not_matched_is_noop():
    org_event = _make_event(
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.NEEDS_ACTION)],
    )
    source = _make_source(events=[org_event])
    module = _build_module({"cal-key": source})

    reply_event = _make_event(
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.ACCEPTED)],
    )
    raw = _build_imip_bytes(reply_event, "REPLY")

    # from_email doesn't match any attendee
    result = module.process_imip_reply(_fake_user(), raw, "nobody@example.com")

    assert result.attendees[0].status == AttendeeStatus.NEEDS_ACTION


def test_reply_wrong_method_raises():
    event = _make_event()
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    raw = _build_imip_bytes(event, "REQUEST")
    with pytest.raises(RequestException) as exc_info:
        module.process_imip_reply(_fake_user(), raw, "x@example.com")
    assert exc_info.value.error == err.ERROR_CALENDAR_IMIP_INVALID_REQUEST


def test_reply_event_not_found_raises():
    source = _make_source(events=[])
    module = _build_module({"cal-key": source})
    event = _make_event(organizer=_organizer(), attendees=[_attendee()])
    raw = _build_imip_bytes(event, "REPLY")
    with pytest.raises(RequestException) as exc_info:
        module.process_imip_reply(_fake_user(), raw, "attendee@example.com")
    assert exc_info.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


def test_reply_does_not_increment_sequence():
    """PARTSTAT update must not change SEQUENCE (RFC 5545 §3.8.7.4)."""
    org_event = _make_event(
        sequence=5,
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.NEEDS_ACTION)],
    )
    source = _make_source(events=[org_event])
    module = _build_module({"cal-key": source})

    reply_event = _make_event(
        sequence=5,
        organizer=_organizer(),
        attendees=[_attendee("attendee@example.com", AttendeeStatus.ACCEPTED)],
    )
    raw = _build_imip_bytes(reply_event, "REPLY")
    result = module.process_imip_reply(_fake_user(), raw, "attendee@example.com")
    assert result.sequence == 5


# ========== Tests for process_imip_request ==========

def test_request_inserts_new_event():
    source = _make_source(events=[])
    module = _build_module({"cal-key": source})

    event = _make_event(organizer=_organizer(), attendees=[_attendee()])
    raw = _build_imip_bytes(event, "REQUEST")

    result = module.process_imip_request(_fake_user(), raw, "organizer@example.com")

    assert len(source.inserted) == 1
    assert result.uid == "evt@example.com"


def test_request_updates_existing_event():
    existing = _make_event(title="Old Title", sequence=1)
    source = _make_source(events=[existing])
    module = _build_module({"cal-key": source})

    updated = _make_event(title="New Title", sequence=2)
    raw = _build_imip_bytes(updated, "REQUEST")

    result = module.process_imip_request(_fake_user(), raw, "organizer@example.com")

    assert result.title == "New Title"
    assert len(source.updated) == 1


def test_request_stale_sequence_ignored():
    existing = _make_event(title="Current", sequence=5)
    source = _make_source(events=[existing])
    module = _build_module({"cal-key": source})

    stale = _make_event(title="Stale", sequence=3)
    raw = _build_imip_bytes(stale, "REQUEST")

    result = module.process_imip_request(_fake_user(), raw, "organizer@example.com")

    assert result.title == "Current"
    assert len(source.updated) == 0


def test_request_does_not_overwrite_reminders():
    personal_reminder = CalReminder(method=ReminderMethod.POPUP, minutes_before=15)
    existing = _make_event(sequence=1, reminders=[personal_reminder])
    source = _make_source(events=[existing])
    module = _build_module({"cal-key": source})

    organizer_event = _make_event(
        title="Updated",
        sequence=2,
        reminders=[CalReminder(method=ReminderMethod.EMAIL, minutes_before=60)],
    )
    raw = _build_imip_bytes(organizer_event, "REQUEST")

    module.process_imip_request(_fake_user(), raw, "organizer@example.com")

    saved = source.updated[0]
    assert len(saved.reminders) == 1
    assert saved.reminders[0].minutes_before == 15


def test_request_no_default_calendar_raises():
    """If the event is not in any calendar and the user has no default calendar, raise NOT_FOUND."""
    module = _build_module({}, default_key="nonexistent")
    event = _make_event(organizer=_organizer(), attendees=[_attendee()])
    raw = _build_imip_bytes(event, "REQUEST")
    with pytest.raises(RequestException) as exc_info:
        module.process_imip_request(_fake_user(), raw, "organizer@example.com")
    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_FOUND


def test_request_wrong_method_raises():
    source = _make_source(events=[])
    module = _build_module({"cal-key": source})
    event = _make_event()
    raw = _build_imip_bytes(event, "CANCEL")
    with pytest.raises(RequestException) as exc_info:
        module.process_imip_request(_fake_user(), raw, "x@example.com")
    assert exc_info.value.error == err.ERROR_CALENDAR_IMIP_INVALID_REQUEST


# ========== Tests for process_imip_cancel ==========

def test_cancel_full_deletes_event():
    event = _make_event()
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})

    cancel_event = _make_event()
    raw = _build_imip_bytes(cancel_event, "CANCEL")

    module.process_imip_cancel(_fake_user(), raw, "organizer@example.com")

    assert "evt@example.com" in source.deleted_uids


def test_cancel_partial_adds_exdate():
    recid = _dt(2026, 6, 8, 9)
    master = _make_event(recurrence_exceptions=[])
    source = _make_source(events=[master])
    module = _build_module({"cal-key": source})

    cancel_event = _make_event(recurrence_id=recid)
    raw = _build_imip_bytes(cancel_event, "CANCEL")

    module.process_imip_cancel(_fake_user(), raw, "organizer@example.com")

    saved = source.updated[0]
    assert recid in saved.recurrence_exceptions
    assert len(source.deleted_uids) == 0


def test_cancel_partial_idempotent():
    """Sending the same partial CANCEL twice should not duplicate the EXDATE."""
    recid = _dt(2026, 6, 8, 9)
    master = _make_event(recurrence_exceptions=[recid])
    source = _make_source(events=[master])
    module = _build_module({"cal-key": source})

    cancel_event = _make_event(recurrence_id=recid)
    raw = _build_imip_bytes(cancel_event, "CANCEL")

    module.process_imip_cancel(_fake_user(), raw, "organizer@example.com")

    # Already in EXDATE — should not update
    assert len(source.updated) == 0


def test_cancel_event_not_found_ignored():
    source = _make_source(events=[])
    module = _build_module({"cal-key": source})

    event = _make_event()
    raw = _build_imip_bytes(event, "CANCEL")

    # Should not raise
    module.process_imip_cancel(_fake_user(), raw, "organizer@example.com")
    assert len(source.deleted_uids) == 0


def test_cancel_wrong_method_raises():
    event = _make_event()
    source = _make_source(events=[event])
    module = _build_module({"cal-key": source})
    raw = _build_imip_bytes(event, "REPLY")
    with pytest.raises(RequestException) as exc_info:
        module.process_imip_cancel(_fake_user(), raw, "x@example.com")
    assert exc_info.value.error == err.ERROR_CALENDAR_IMIP_INVALID_REQUEST
