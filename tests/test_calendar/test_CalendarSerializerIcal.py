"""Unit tests for CalCalendarSerializerIcal - the VCALENDAR wrapping and calendar-level header."""
from datetime import datetime, timedelta, timezone

import pytest

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalEventSerializerIcal import CalEventSerializerIcal
from app.module.calendar.serializer.CalEventsSerializerIcal import CalEventsSerializerIcal
from app.module.calendar.serializer.CalCalendarSerializerIcal import CalCalendarSerializerIcal

_UTC = timezone.utc


def _serializer(refresh_interval=None):
    return CalCalendarSerializerIcal(
        CalEventsSerializerIcal(CalEventSerializerIcal()), refresh_interval=refresh_interval,
    )


def _calendar(**kwargs):
    cal = CalCalendar(user_uid="u@example.com", name=kwargs.pop("name", "My Calendar"), **kwargs)
    return cal


def _event(uid="e@e.com"):
    return CalEvent(uid=uid, title="E", date_start=datetime(2026, 1, 1, tzinfo=_UTC),
                    date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC))


def test_vcalendar_envelope_and_required_properties():
    cal = _calendar()
    cal.events = [_event()]
    out = _serializer().serialize(cal)
    lines = out.splitlines()
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    assert "VERSION:2.0" in out
    assert "PRODID:" in out
    assert "BEGIN:VEVENT" in out


def test_header_carries_calendar_descriptors():
    cal = _calendar(name="Work", description="Pro stuff", timezone="Europe/Paris")
    out = _serializer().serialize(cal)
    assert "X-WR-CALNAME:Work" in out
    assert "X-WR-CALDESC:Pro stuff" in out
    assert "X-WR-TIMEZONE:Europe/Paris" in out


def test_caldesc_absent_when_no_description():
    cal = _calendar(description=None)
    assert "X-WR-CALDESC" not in _serializer().serialize(cal)


def test_body_dispatches_vevent_and_vtodo():
    cal = _calendar()
    cal.events = [
        _event(),
        CalEvent(uid="t@t.com", title="T", date_start=datetime(2026, 1, 1, tzinfo=_UTC),
                 date_end=datetime(2026, 1, 31, tzinfo=_UTC), component_type=ComponentType.TASK),
    ]
    out = _serializer().serialize(cal)
    assert "BEGIN:VEVENT" in out
    assert "BEGIN:VTODO" in out


def test_refresh_interval_emitted_when_set():
    out = _serializer(refresh_interval=timedelta(hours=12)).serialize(_calendar())
    assert "REFRESH-INTERVAL" in out
    assert "X-PUBLISHED-TTL" in out
    assert "PT12H" in out


def test_refresh_interval_absent_by_default():
    out = _serializer().serialize(_calendar())
    assert "REFRESH-INTERVAL" not in out
    assert "X-PUBLISHED-TTL" not in out


def test_extra_properties_emitted():
    cal = _calendar()
    cal.extra_properties = {"X-CUSTOM-FLAG": "yes"}
    assert "X-CUSTOM-FLAG:yes" in _serializer().serialize(cal)
