"""
Unit tests for CalendarEventsDeserializerIcal.
Verifies that a full VCALENDAR block is correctly parsed into a list of CalEvent objects.

RFC 5545 examples: https://icalendar.org/iCalendar-RFC-5545/4-icalendar-object-examples.html
"""
import pytest

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.utils.exceptions import RequestException
from tests.test_calendar.ical_examples import (
    ICAL_EXAMPLE_1,
    ICAL_EXAMPLE_2,
    ICAL_EXAMPLE_4,
    ICAL_EXAMPLE_5,
    ICAL_EXAMPLE_6,
)

ICAL_MULTI_EVENT = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Multi//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:evt1@example.com\r\n"
    "SUMMARY:Event One\r\n"
    "DTSTART:20260101T090000Z\r\n"
    "DTEND:20260101T100000Z\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:evt2@example.com\r\n"
    "SUMMARY:Event Two\r\n"
    "DTSTART:20260102T090000Z\r\n"
    "DTEND:20260102T100000Z\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


@pytest.fixture
def deserializer():
    return CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal())


def test_single_event_parsed(deserializer):
    events = deserializer.deserialize(ICAL_EXAMPLE_1)
    assert len(events) == 1
    assert events[0].uid == "uid1@example.com"


def test_multi_event_count(deserializer):
    assert len(deserializer.deserialize(ICAL_MULTI_EVENT)) == 2


def test_vtimezone_not_yielded_as_event(deserializer):
    assert len(deserializer.deserialize(ICAL_EXAMPLE_2)) == 1


def test_vtodo_parsed_as_task(deserializer):
    events = deserializer.deserialize(ICAL_EXAMPLE_4)
    assert len(events) == 1
    assert events[0].component_type == ComponentType.TASK
    assert events[0].uid == "uid4@example.com"


def test_vjournal_gives_empty_list(deserializer):
    assert deserializer.deserialize(ICAL_EXAMPLE_5) == []


def test_vfreebusy_gives_empty_list(deserializer):
    assert deserializer.deserialize(ICAL_EXAMPLE_6) == []


def test_invalid_ics_raises(deserializer):
    with pytest.raises(RequestException):
        deserializer.deserialize("not valid ics")


ICAL_MIXED = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:event@example.com\r\n"
    "SUMMARY:A meeting\r\n"
    "DTSTART:20260101T090000Z\r\n"
    "DTEND:20260101T100000Z\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VTODO\r\n"
    "UID:task@example.com\r\n"
    "SUMMARY:A task\r\n"
    "DUE:20260131T235959Z\r\n"
    "END:VTODO\r\n"
    "END:VCALENDAR\r\n"
)


def test_mixed_component_types(deserializer):
    components = {e.component_type for e in deserializer.deserialize(ICAL_MIXED)}
    assert components == {ComponentType.EVENT, ComponentType.TASK}
