"""
Unit tests for CalendarEventDeserializerIcal.
RFC 5545 Section 4 examples: https://icalendar.org/iCalendar-RFC-5545/4-icalendar-object-examples.html
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from tests.test_calendar.ical_examples import (
    ICAL_EXAMPLE_1,
    ICAL_EXAMPLE_2,
    ICAL_EXAMPLE_3,
    ICAL_EXAMPLE_4,
)

ICAL_ALLDAY = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20240101T000000Z\r\n"
    "UID:allday@test.com\r\n"
    "DTSTART;VALUE=DATE:20240315\r\n"
    "DTEND;VALUE=DATE:20240316\r\n"
    "SUMMARY:All-Day Event\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

ICAL_RRULE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20240101T000000Z\r\n"
    "UID:rrule@test.com\r\n"
    "DTSTART:20240101T090000Z\r\n"
    "DTEND:20240101T100000Z\r\n"
    "SUMMARY:Weekly Monday Meeting\r\n"
    "RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=10\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

ICAL_VALARM = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20240101T000000Z\r\n"
    "UID:alarm@test.com\r\n"
    "DTSTART:20240315T090000Z\r\n"
    "DTEND:20240315T100000Z\r\n"
    "SUMMARY:Meeting with Alarm\r\n"
    "BEGIN:VALARM\r\n"
    "ACTION:DISPLAY\r\n"
    "TRIGGER:-PT15M\r\n"
    "DESCRIPTION:Reminder\r\n"
    "END:VALARM\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

ICAL_TEXT_ESCAPE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20240101T000000Z\r\n"
    "UID:escape@test.com\r\n"
    "DTSTART:20240101T090000Z\r\n"
    "DTEND:20240101T100000Z\r\n"
    "SUMMARY:Meeting\\; Planning\\, Review\r\n"
    "DESCRIPTION:Line one\\nLine two\\\\backslash\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


@pytest.fixture
def deserializer():
    """Return a fresh deserializer instance."""
    return CalendarEventDeserializerIcal()


# ==========================================================================
# Example 1 — Three-Day Conference
# ==========================================================================

def test_example1_uid(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.uid == "uid1@example.com"


def test_example1_title(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.title == "Networld+Interop Conference"


def test_example1_dates(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.date_start == datetime(1996, 9, 18, 14, 30, 0, tzinfo=timezone.utc)
    assert event.date_end == datetime(1996, 9, 20, 22, 0, 0, tzinfo=timezone.utc)
    assert not event.all_day


def test_example1_organizer(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.organizer is not None
    assert event.organizer.email == "jsmith@example.com"


def test_example1_status(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.status == EventStatus.CONFIRMED


def test_example1_categories(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.categories == ["CONFERENCE"]


def test_example1_description_unescaping(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.description is not None
    # \n escape sequences in TEXT must be unescaped to actual newlines
    assert "\n" in event.description
    # \, must be unescaped to a plain comma
    assert "Atlanta, Georgia" in event.description
    assert "Exhibit" in event.description


def test_example1_description_unfolding(deserializer):
    # The DESCRIPTION is folded across multiple lines; unfolding must produce continuous text
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert "Congress Center" in event.description


# ==========================================================================
# Example 2 — Group-Scheduled Meeting with Timezone
# ==========================================================================

def test_example2_uid(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert event.uid == "guid-1.example.com"


def test_example2_title_and_location(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert event.title == "XYZ Project Review"
    assert event.location == "1CP Conference Room 4350"


def test_example2_timezone_conversion(deserializer):
    # 1998-03-12 is before US DST (started 1998-04-05), so NY is at UTC-5 (EST)
    # 08:30 EST = 13:30 UTC, 09:30 EST = 14:30 UTC
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert event.date_start == datetime(1998, 3, 12, 13, 30, 0, tzinfo=timezone.utc)
    assert event.date_end == datetime(1998, 3, 12, 14, 30, 0, tzinfo=timezone.utc)
    assert event.timezone == "America/New_York"
    assert not event.all_day


def test_example2_attendee(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert len(event.attendees) == 1
    attendee = event.attendees[0]
    assert attendee.email == "employee-A@example.com"
    assert attendee.role == AttendeeRole.REQUIRED
    assert attendee.cutype == CalUserType.GROUP
    assert attendee.rsvp is True


def test_example2_visibility_and_created(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert event.visibility == EventVisibility.PUBLIC
    assert event.created_at == datetime(1998, 3, 9, 13, 0, 0, tzinfo=timezone.utc)


def test_example2_categories(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_2)
    assert event.categories == ["MEETING"]


# ==========================================================================
# Example 3 — Multiple Categories and URI Attachment
# ==========================================================================

def test_example3_uid_and_sequence(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_3)
    assert event.uid == "uid3@example.com"
    assert event.sequence == 0


def test_example3_categories(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_3)
    assert "MEETING" in event.categories
    assert "PROJECT" in event.categories
    assert len(event.categories) == 2


def test_example3_attachment(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_3)
    assert len(event.attachments) == 1
    attach = event.attachments[0]
    assert attach.url == "ftp://example.com/pub/conf/bkgrnd.ps"
    assert attach.mime_type == "application/postscript"


def test_example3_attendee(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_3)
    assert len(event.attendees) == 1
    assert event.attendees[0].email == "jsmith@example.com"
    assert event.attendees[0].rsvp is True


def test_example3_description_continuation(deserializer):
    # DESCRIPTION is folded and contains a \n TEXT escape
    event = deserializer.deserialize(ICAL_EXAMPLE_3)
    assert event.description is not None
    assert "interoperability" in event.description
    assert "iCalendar" in event.description
    # The \n TEXT escape in the RFC example is unescaped to an actual newline
    assert "\n" in event.description


# ==========================================================================
# All-day event (DATE value type)
# ==========================================================================

def test_allday_flag(deserializer):
    event = deserializer.deserialize(ICAL_ALLDAY)
    assert event.all_day is True


def test_allday_dates(deserializer):
    event = deserializer.deserialize(ICAL_ALLDAY)
    assert event.date_start.year == 2024
    assert event.date_start.month == 3
    assert event.date_start.day == 15


# ==========================================================================
# RRULE
# ==========================================================================

def test_rrule_frequency(deserializer):
    event = deserializer.deserialize(ICAL_RRULE)
    assert event.recurrence_rule is not None
    assert event.recurrence_rule.frequency == RecurrenceFrequency.WEEKLY


def test_rrule_byday_and_count(deserializer):
    event = deserializer.deserialize(ICAL_RRULE)
    rule = event.recurrence_rule
    assert rule.by_day == ["MO"]
    assert rule.count == 10
    assert rule.until is None


# ==========================================================================
# VALARM
# ==========================================================================

def test_valarm_popup(deserializer):
    event = deserializer.deserialize(ICAL_VALARM)
    assert len(event.reminders) == 1
    reminder = event.reminders[0]
    assert reminder.method == ReminderMethod.POPUP
    assert reminder.minutes_before == 15


# ==========================================================================
# TEXT escaping (§3.3.11)
# ==========================================================================

def test_text_unescape_semicolon_and_comma(deserializer):
    event = deserializer.deserialize(ICAL_TEXT_ESCAPE)
    assert event.title == "Meeting; Planning, Review"


def test_text_unescape_newline_and_backslash(deserializer):
    event = deserializer.deserialize(ICAL_TEXT_ESCAPE)
    assert event.description == "Line one\nLine two\\backslash"


# ==========================================================================
# EXDATE
# ==========================================================================

ICAL_EXDATE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20260101T000000Z\r\n"
    "UID:exdate@test.com\r\n"
    "DTSTART:20260105T090000Z\r\n"
    "DTEND:20260105T100000Z\r\n"
    "SUMMARY:Daily Meeting\r\n"
    "RRULE:FREQ=DAILY;COUNT=5\r\n"
    "EXDATE:20260106T090000Z,20260108T090000Z\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_exdate_parsed(deserializer):
    event = deserializer.deserialize(ICAL_EXDATE)
    assert event.recurrence_exceptions is not None
    assert len(event.recurrence_exceptions) == 2
    excluded = {dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt for dt in event.recurrence_exceptions}
    assert datetime(2026, 1, 6, 9, 0, 0, tzinfo=timezone.utc) in excluded
    assert datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc) in excluded


# ==========================================================================
# RECURRENCE-ID
# ==========================================================================

ICAL_RECURRENCE_ID = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20260101T000000Z\r\n"
    "UID:recurrence-id@test.com\r\n"
    "DTSTART:20260105T090000Z\r\n"
    "DTEND:20260105T100000Z\r\n"
    "SUMMARY:Daily Meeting\r\n"
    "RRULE:FREQ=DAILY;COUNT=3\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20260101T000000Z\r\n"
    "UID:recurrence-id@test.com\r\n"
    "RECURRENCE-ID:20260106T090000Z\r\n"
    "DTSTART:20260106T100000Z\r\n"
    "DTEND:20260106T110000Z\r\n"
    "SUMMARY:Modified Jan 6\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_recurrence_id_parsed(deserializer):
    """Override VEVENT must have recurrence_id pointing to the original occurrence datetime."""
    events_deserializer = CalendarEventsDeserializerIcal(deserializer)
    events = events_deserializer.deserialize(ICAL_RECURRENCE_ID)

    overrides = [e for e in events if e.recurrence_id is not None]
    assert len(overrides) == 1
    override = overrides[0]
    assert override.uid == "recurrence-id@test.com"
    assert override.title == "Modified Jan 6"
    recurrence_id = override.recurrence_id
    if recurrence_id.tzinfo is None:
        recurrence_id = recurrence_id.replace(tzinfo=timezone.utc)
    assert recurrence_id == datetime(2026, 1, 6, 9, 0, 0, tzinfo=timezone.utc)


# ==========================================================================
# VTODO
# ==========================================================================

ICAL_VTODO_FULL = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VTODO\r\n"
    "DTSTAMP:20260101T000000Z\r\n"
    "UID:todo@test.com\r\n"
    "DTSTART:20260101T090000Z\r\n"
    "DUE:20260131T235959Z\r\n"
    "SUMMARY:Prepare report\r\n"
    "STATUS:IN-PROCESS\r\n"
    "PERCENT-COMPLETE:50\r\n"
    "COMPLETED:20260115T120000Z\r\n"
    "CLASS:PRIVATE\r\n"
    "END:VTODO\r\n"
    "END:VCALENDAR\r\n"
)

ICAL_VTODO_NO_STATUS = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VTODO\r\n"
    "DTSTAMP:20260101T000000Z\r\n"
    "UID:todo-nostatus@test.com\r\n"
    "DUE:20260131T235959Z\r\n"
    "SUMMARY:Task without status\r\n"
    "END:VTODO\r\n"
    "END:VCALENDAR\r\n"
)


def test_vtodo_component_type(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert event.component_type == ComponentType.TASK


def test_vtodo_uid(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert event.uid == "uid4@example.com"


def test_vtodo_title(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert event.title == "Submit Income Taxes"


def test_vtodo_status_needs_action(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert event.status == EventStatus.NEEDS_ACTION


def test_vtodo_due_maps_to_date_end(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_4)
    # DUE:19980415T000000 (naive → UTC)
    assert event.date_end == datetime(1998, 4, 15, 0, 0, 0, tzinfo=timezone.utc)


def test_vtodo_status_in_process(deserializer):
    event = deserializer.deserialize(ICAL_VTODO_FULL)
    assert event.status == EventStatus.IN_PROCESS


def test_vtodo_percent_complete(deserializer):
    event = deserializer.deserialize(ICAL_VTODO_FULL)
    assert event.percent_complete == 50


def test_vtodo_completed_at(deserializer):
    event = deserializer.deserialize(ICAL_VTODO_FULL)
    assert event.completed_at == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_vtodo_no_status_defaults_to_needs_action(deserializer):
    event = deserializer.deserialize(ICAL_VTODO_NO_STATUS)
    assert event.status == EventStatus.NEEDS_ACTION


def test_vevent_component_type(deserializer):
    event = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert event.component_type == ComponentType.EVENT


# ==========================================================================
# PRIORITY (RFC 5545 §3.8.1.9)
# ==========================================================================

_ICAL_PRIORITY = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTAMP:20240101T000000Z\r\n"
    "UID:prio@test.com\r\n"
    "DTSTART:20240101T090000Z\r\n"
    "DTEND:20240101T100000Z\r\n"
    "SUMMARY:Priority Event\r\n"
    "PRIORITY:5\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_priority_parsed(deserializer):
    event = deserializer.deserialize(_ICAL_PRIORITY)
    assert event.priority == 5


def test_priority_defaults_to_zero_when_absent(deserializer):
    event = deserializer.deserialize(ICAL_ALLDAY)
    assert event.priority == 0
