"""Unit tests for CalendarDeserializerIcal — VCALENDAR header parsing + event delegation."""
import pytest

from app.module.calendar.serializer.CalendarDeserializerIcal import CalendarDeserializerIcal
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.utils.exceptions import RequestException


@pytest.fixture
def deserializer():
    return CalendarDeserializerIcal(CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal()))


_ICS = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "CALSCALE:GREGORIAN\r\n"
    "X-WR-CALNAME:Holidays\r\n"
    "X-WR-CALDESC:Public holidays\r\n"
    "X-WR-TIMEZONE:Europe/Paris\r\n"
    "X-CUSTOM-PROP:abc\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:evt-1@test\r\n"
    "SUMMARY:New Year\r\n"
    "DTSTART:20260101T090000Z\r\n"
    "DTEND:20260101T100000Z\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_parses_calendar_header(deserializer):
    cal = deserializer.deserialize(_ICS)
    assert cal.name == "Holidays"
    assert cal.description == "Public holidays"
    assert cal.timezone == "Europe/Paris"
    assert "Test" in cal.prodid


def test_populates_events(deserializer):
    cal = deserializer.deserialize(_ICS)
    assert len(cal.events) == 1
    assert cal.events[0].uid == "evt-1@test"


def test_unmapped_property_kept_in_extra(deserializer):
    cal = deserializer.deserialize(_ICS)
    assert cal.extra_properties.get("X-CUSTOM-PROP") == "abc"
    assert "X-WR-CALNAME" not in cal.extra_properties


def test_timezone_defaults_to_utc_when_absent(deserializer):
    ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//T//EN\r\nX-WR-CALNAME:NoTz\r\nEND:VCALENDAR\r\n"
    assert deserializer.deserialize(ics).timezone == "UTC"


def test_invalid_ics_raises(deserializer):
    with pytest.raises(RequestException):
        deserializer.deserialize("not valid ics")
