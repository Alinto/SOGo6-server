"""Unit tests for AttendanceProcessor, the core shared by both response paths."""
import dataclasses
from datetime import datetime, timezone

import pytest

from app.module.calendar.attendance.AttendanceProcessor import AttendanceProcessor
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException

_UTC = timezone.utc
_OCC = datetime(2037, 6, 8, 9, tzinfo=_UTC)


def _dt(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=_UTC)


def _attendee(email="bob@example.com", status=AttendeeStatus.NEEDS_ACTION):
    return CalAttendee(email=email, name="Bob", status=status)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        key="evt-key",
        title="Meeting",
        date_start=_dt(2037, 6, 1, 9),
        date_end=_dt(2037, 6, 1, 10),
        organizer=CalOrganizer(email="alice@example.com", name="Alice"),
        attendees=[_attendee()],
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


class FakeSource(CalendarSource):
    """Tracks writes, propagations and detachments so each gate can be observed."""

    def __init__(self, calendar, occurrence=None):
        super().__init__(calendar)
        self._occurrence = occurrence
        self.updated = []
        self.propagated = []
        self.detached = []

    def is_writable(self):
        return True

    def _fetch_events(self, start, end, search=None):
        return []

    def get_event_by_recurrence_id(self, uid, recurrence_id):
        return self._occurrence

    def get_or_create_occurrence(self, master, recurrence_id):
        self.detached.append(recurrence_id)
        # A detached row owns its attendee list and inherits the series revision.
        self._occurrence = dataclasses.replace(
            master, key="occ-key", recurrence_id=recurrence_id, recurrence_rule=None,
            attendees=[dataclasses.replace(a) for a in master.attendees],
        )
        return self._occurrence

    def update_event(self, event):
        self.updated.append(event)

    def propagate_partstat_to_copies(self, event, attendee_email, status):
        self.propagated.append((event.key, attendee_email, status))

    def update_calendar(self, calendar):
        self._calendar = calendar


def _source(occurrence=None):
    return FakeSource(CalCalendar(key="cal-key", user_uid="alice@example.com", name="Cal", ctag=0), occurrence)


# ========== Applying ==========

def test_applies_and_propagates():
    event = _make_event()
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0,
    )

    assert result.attendees[0].status == AttendeeStatus.ACCEPTED
    assert len(source.updated) == 1
    assert source.propagated == [("evt-key", "bob@example.com", AttendeeStatus.ACCEPTED)]


def test_already_current_writes_nothing():
    event = _make_event(attendees=[_attendee(status=AttendeeStatus.ACCEPTED)])
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0,
    )

    assert result is event
    assert not source.updated
    assert not source.propagated


def test_not_an_attendee_raises():
    event = _make_event(attendees=[_attendee("someone.else@example.com")])
    source = _source()

    with pytest.raises(RequestException) as exc_info:
        AttendanceProcessor.apply_response(
            source=source, event=event, attendee_email="bob@example.com",
            status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0,
        )

    assert exc_info.value.error == err.ERROR_CALENDAR_NOT_ATTENDEE
    assert not source.updated


# ========== Revision ==========

def test_obsolete_revision_is_refused():
    event = _make_event(sequence=3)
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=2,
    )

    assert result is None
    assert not source.updated
    assert event.attendees[0].status == AttendeeStatus.NEEDS_ACTION


def test_same_or_newer_revision_is_applied():
    for incoming in (3, 4):
        event = _make_event(sequence=3)
        source = _source()

        result = AttendanceProcessor.apply_response(
            source=source, event=event, attendee_email="bob@example.com",
            status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=incoming,
        )

        assert result.attendees[0].status == AttendeeStatus.ACCEPTED


# ========== Reply ordering (RFC 5546 2.1.5) ==========

def test_first_reply_records_the_couple():
    event = _make_event()
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0,
    )

    assert result.attendees[0].reply_sequence == 0
    assert result.attendees[0].reply_dtstamp == _dt(2037, 6, 1, 8)


def test_out_of_order_reply_is_discarded():
    """The attendee's earlier answer delivered late must not override their latest one."""
    att = _attendee(status=AttendeeStatus.DECLINED)
    att.reply_sequence = 0
    att.reply_dtstamp = _dt(2037, 6, 1, 10)
    event = _make_event(attendees=[att])
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 9), incoming_sequence=0,
    )

    assert result is None
    assert event.attendees[0].status == AttendeeStatus.DECLINED
    assert not source.updated


def test_replayed_reply_is_discarded():
    """An identical (SEQUENCE, DTSTAMP) couple is a duplicate delivery, not a newer answer."""
    att = _attendee(status=AttendeeStatus.DECLINED)
    att.reply_sequence = 0
    att.reply_dtstamp = _dt(2037, 6, 1, 10)
    event = _make_event(attendees=[att])
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 10), incoming_sequence=0,
    )

    assert result is None
    assert not source.updated


def test_newer_reply_supersedes_and_updates_the_couple():
    att = _attendee(status=AttendeeStatus.ACCEPTED)
    att.reply_sequence = 0
    att.reply_dtstamp = _dt(2037, 6, 1, 10)
    event = _make_event(attendees=[att])
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=event, attendee_email="bob@example.com",
        status=AttendeeStatus.DECLINED, incoming_dtstamp=_dt(2037, 6, 1, 11), incoming_sequence=0,
    )

    assert result.attendees[0].status == AttendeeStatus.DECLINED
    assert result.attendees[0].reply_dtstamp == _dt(2037, 6, 1, 11)


# ========== Occurrences ==========

def test_recurrence_id_detaches_and_leaves_the_master_alone():
    master = _make_event(sequence=2)
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=master, attendee_email="bob@example.com",
        status=AttendeeStatus.DECLINED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=2, recurrence_id=_OCC,
    )

    assert result.recurrence_id == _OCC
    assert result.attendees[0].status == AttendeeStatus.DECLINED
    assert master.attendees[0].status == AttendeeStatus.NEEDS_ACTION
    assert source.detached == [_OCC]


def test_existing_occurrence_is_reused():
    master = _make_event()
    occurrence = _make_event(key="occ-key", recurrence_id=_OCC)
    source = _source(occurrence=occurrence)

    result = AttendanceProcessor.apply_response(
        source=source, event=master, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0, recurrence_id=_OCC,
    )

    assert result is occurrence
    assert not source.detached


def test_refused_response_does_not_detach():
    """Detaching writes an EXDATE on the master, so a refused answer must stop before it."""
    master = _make_event(sequence=5)
    source = _source()

    result = AttendanceProcessor.apply_response(
        source=source, event=master, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=1, recurrence_id=_OCC,
    )

    assert result is None
    assert not source.detached
    assert not source.updated


def test_reply_to_a_cancelled_occurrence_is_refused():
    """An EXDATE with no live row is a cancelled slot: re-materializing it would resurrect it."""
    master = _make_event(recurrence_exceptions=[_OCC])
    source = _source()

    with pytest.raises(RequestException) as exc_info:
        AttendanceProcessor.apply_response(
            source=source, event=master, attendee_email="bob@example.com",
            status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=0, recurrence_id=_OCC,
        )

    assert exc_info.value.error == err.ERROR_CALENDAR_OCCURRENCE_NOT_FOUND
    assert not source.detached
    assert not source.updated


def test_gates_read_the_master_until_the_occurrence_exists():
    """The instance inherits the series revision, so the master is what arbitrates the first answer."""
    master = _make_event(sequence=4)
    source = _source()

    refused = AttendanceProcessor.apply_response(
        source=source, event=master, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=3, recurrence_id=_OCC,
    )
    assert refused is None

    applied = AttendanceProcessor.apply_response(
        source=source, event=master, attendee_email="bob@example.com",
        status=AttendeeStatus.ACCEPTED, incoming_dtstamp=_dt(2037, 6, 1, 8), incoming_sequence=4, recurrence_id=_OCC,
    )
    assert applied.recurrence_id == _OCC
