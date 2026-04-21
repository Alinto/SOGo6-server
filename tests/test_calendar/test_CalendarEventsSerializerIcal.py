"""
Unit tests for CalendarEventsSerializerIcal.
Verifies that a list of CalEvent objects is correctly serialized into a
RFC 5545-compliant VCALENDAR string.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal
from app.module.calendar.serializer.CalendarEventsSerializerIcal import CalendarEventsSerializerIcal


@pytest.fixture
def serializer():
    return CalendarEventsSerializerIcal(CalendarEventSerializerIcal())


@pytest.fixture
def one_event():
    return [CalEvent(
        uid="evt@example.com",
        title="Standup",
        date_start=datetime(2026, 3, 19, 9, 30, tzinfo=timezone.utc),
        date_end=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
    )]


def test_returns_string(serializer, one_event):
    assert isinstance(serializer.serialize(one_event), str)


def test_vcalendar_wrapper(serializer, one_event):
    lines = serializer.serialize(one_event).splitlines()
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"


def test_version(serializer, one_event):
    assert "VERSION:2.0" in serializer.serialize(one_event)


def test_prodid_present(serializer, one_event):
    assert "PRODID:" in serializer.serialize(one_event)


def test_contains_vevent(serializer, one_event):
    result = serializer.serialize(one_event)
    assert "BEGIN:VEVENT" in result
    assert "END:VEVENT" in result


def test_empty_list_no_vevent(serializer):
    result = serializer.serialize([])
    assert "BEGIN:VEVENT" not in result


def test_multiple_events(serializer):
    events = [
        CalEvent(
            uid=f"e{i}@example.com", title=f"E{i}",
            date_start=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            date_end=datetime(2026, 1, i + 1, 1, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    result = serializer.serialize(events)
    assert result.count("BEGIN:VEVENT") == 3
