"""Unit tests for CalCalendarTimezoneSerializerIcal - the VCALENDAR holding the VTIMEZONE of a calendar."""

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalCalendarTimezoneSerializerIcal import CalCalendarTimezoneSerializerIcal


def _serialize(timezone):
    return CalCalendarTimezoneSerializerIcal().serialize(
        CalCalendar(user_uid="u@example.com", name="Work", timezone=timezone)
    )


# ========== Tests for serialize ==========


def test_one_vtimezone_of_the_calendar():
    ics = _serialize("Europe/Paris")
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.count("BEGIN:VTIMEZONE") == 1
    assert "TZID:Europe/Paris\r\n" in ics
    assert "BEGIN:VEVENT" not in ics


def test_unknown_timezone_written_as_utc():
    assert "TZID:UTC\r\n" in _serialize("Mars/Olympus")
