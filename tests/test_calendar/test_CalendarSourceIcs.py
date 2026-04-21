"""
Unit tests for CalendarSourceIcs.

Covers:
- Timezone-aware filtering: events with TZID are converted to UTC before comparison
- RRULE expansion pipeline: EXDATE, RECURRENCE-ID override
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import urllib.error

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.module.calendar.source.CalendarSourceIcs import CalendarSourceIcs
from app.utils.errors import ERROR_CALENDAR_ICS_FETCH_FAILED
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _ics(uid, summary, dtstart, dtend):
    """Build a minimal VCALENDAR with one VEVENT. dtstart/dtend are raw iCal property values."""
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DTSTART{dtstart}\r\n"
        f"DTEND{dtend}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@pytest.fixture
def source():
    calendar = CalCalendar(user_uid="test", name="Test", source_type="ics")
    deserializer = CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal())
    return CalendarSourceIcs(calendar=calendar, ics_url="https://example.com/cal.ics", deserializer=deserializer)


# ========== Timezone-aware filtering (TZID -> UTC) ==========

def test_paris_winter_cet_included(source):
    """
    Event 23:00-01:00 Europe/Paris on Jan 15/16 (CET = UTC+1) → 22:00-00:00 UTC.
    Filter end: 22:30 UTC Jan 15.
    Local view: start 23:00 > 22:30 → would be excluded naively.
    UTC view: start 22:00 <= 22:30 → must be included.
    """
    ics = _ics(
        uid="paris-winter@example.com",
        summary="Late Paris Meeting (winter)",
        dtstart=";TZID=Europe/Paris:20260115T230000",
        dtend=";TZID=Europe/Paris:20260116T010000",
    )
    with patch.object(source, "_fetch_ics", return_value=ics):
        events = source.get_events(
            start=_dt(2026, 1, 15, 0),
            end=datetime(2026, 1, 15, 22, 30, tzinfo=_UTC),
        )
    assert any(e.uid == "paris-winter@example.com" for e in events)


def test_paris_summer_cest_included(source):
    """
    Event 23:00-01:00 Europe/Paris on Jul 15/16 (CEST = UTC+2) → 21:00-23:00 UTC.
    Filter end: 21:30 UTC Jul 15.
    Local view: start 23:00 > 21:30 → would be excluded naively.
    UTC view: start 21:00 <= 21:30 → must be included.
    """
    ics = _ics(
        uid="paris-summer@example.com",
        summary="Late Paris Meeting (summer)",
        dtstart=";TZID=Europe/Paris:20260715T230000",
        dtend=";TZID=Europe/Paris:20260716T010000",
    )
    with patch.object(source, "_fetch_ics", return_value=ics):
        events = source.get_events(
            start=_dt(2026, 7, 15, 0),
            end=datetime(2026, 7, 15, 21, 30, tzinfo=_UTC),
        )
    assert any(e.uid == "paris-summer@example.com" for e in events)


def test_new_york_est_excluded(source):
    """
    Event 20:00-21:00 America/New_York on Jan 15 (EST = UTC-5) → 01:00-02:00 UTC on Jan 16.
    Filter: Jan 15 00:00-23:59 UTC.
    Local view: start 20:00 Jan 15 <= 23:59 → would be included naively.
    UTC view: start 01:00 Jan 16 > 23:59 Jan 15 → must be excluded.
    """
    ics = _ics(
        uid="newyork@example.com",
        summary="New York Evening Event",
        dtstart=";TZID=America/New_York:20260115T200000",
        dtend=";TZID=America/New_York:20260115T210000",
    )
    with patch.object(source, "_fetch_ics", return_value=ics):
        events = source.get_events(
            start=_dt(2026, 1, 15, 0),
            end=datetime(2026, 1, 15, 23, 59, tzinfo=_UTC),
        )
    assert not any(e.uid == "newyork@example.com" for e in events)


# ========== RRULE + EXDATE pipeline ==========

ICS_RRULE_WITH_EXDATE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:rrule-exdate@example.com\r\n"
    "SUMMARY:Daily Meeting\r\n"
    "DTSTART:20260105T090000Z\r\n"
    "DTEND:20260105T100000Z\r\n"
    "RRULE:FREQ=DAILY;COUNT=3\r\n"
    "EXDATE:20260106T090000Z\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_pipeline_exdate(source):
    """DAILY;COUNT=3 starting Jan 5, EXDATE removes Jan 6 → only Jan 5 and Jan 7."""
    with patch.object(source, "_fetch_ics", return_value=ICS_RRULE_WITH_EXDATE):
        events = source.get_events(start=_dt(2026, 1, 5), end=_dt(2026, 1, 8))
    starts = [e.date_start for e in events]
    assert datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC) in starts
    assert datetime(2026, 1, 6, 9, 0, 0, tzinfo=_UTC) not in starts
    assert datetime(2026, 1, 7, 9, 0, 0, tzinfo=_UTC) in starts
    assert len(events) == 2


# ========== RRULE + RECURRENCE-ID pipeline ==========

ICS_RRULE_WITH_OVERRIDE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:rrule-override@example.com\r\n"
    "SUMMARY:Daily Meeting\r\n"
    "DTSTART:20260105T090000Z\r\n"
    "DTEND:20260105T100000Z\r\n"
    "RRULE:FREQ=DAILY;COUNT=3\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:rrule-override@example.com\r\n"
    "RECURRENCE-ID:20260106T090000Z\r\n"
    "DTSTART:20260106T100000Z\r\n"
    "DTEND:20260106T110000Z\r\n"
    "SUMMARY:Modified Jan 6\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_pipeline_recurrence_id_override(source):
    """DAILY;COUNT=3, override replaces Jan 6 at 09:00 with a modified occurrence at 10:00."""
    with patch.object(source, "_fetch_ics", return_value=ICS_RRULE_WITH_OVERRIDE):
        events = source.get_events(start=_dt(2026, 1, 5), end=_dt(2026, 1, 8))
    assert len(events) == 3
    jan6 = next(e for e in events if e.date_start == datetime(2026, 1, 6, 10, 0, 0, tzinfo=_UTC))
    assert jan6.title == "Modified Jan 6"
    assert not any(e.date_start == datetime(2026, 1, 6, 9, 0, 0, tzinfo=_UTC) for e in events)


# ========== Error handling ==========

def test_fetch_url_error_raises_request_exception(source):
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        with pytest.raises(RequestException) as exc_info:
            source._fetch_ics()
    assert exc_info.value.error == ERROR_CALENDAR_ICS_FETCH_FAILED


def test_fetch_http_error_raises_request_exception(source):
    http_err = urllib.error.HTTPError(url=None, code=404, msg="Not Found", hdrs=None, fp=None)
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(RequestException) as exc_info:
            source._fetch_ics()
    assert exc_info.value.error == ERROR_CALENDAR_ICS_FETCH_FAILED
