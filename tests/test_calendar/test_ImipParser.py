"""Unit tests for ImipParser."""
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from app.module.calendar.imip.ImipMethod import ImipMethod
from app.module.calendar.imip.ImipParser import ImipParser
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalEventSerializerIcal import CalEventSerializerIcal
from app.utils.errors import ERROR_CALENDAR_ICS_PARSE_FAILED, ERROR_CALENDAR_IMIP_INVALID_REQUEST
from app.utils.exceptions import RequestException


_serializer = CalEventSerializerIcal()


def _make_event():
    return CalEvent(
        uid="test-uid@example.com",
        title="Meeting",
        date_start=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        date_end=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    )


def _build_email(ical: str, from_addr: str = "alice@example.com", to_addr: str = "bob@example.com") -> bytes:
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "Invite"
    msg.attach(MIMEText(ical, "calendar", "utf-8"))
    return msg.as_bytes()


# ========== Tests for ImipParser.parse ==========

def test_parse_request_method():
    ical = _serializer.build_imip(_make_event(), "REQUEST")
    raw = _build_email(ical)
    result = ImipParser.parse(raw)
    assert result.method == ImipMethod.REQUEST


def test_parse_reply_method():
    ical = _serializer.build_imip(_make_event(), "REPLY")
    raw = _build_email(ical)
    result = ImipParser.parse(raw)
    assert result.method == ImipMethod.REPLY


def test_parse_cancel_method():
    ical = _serializer.build_imip(_make_event(), "CANCEL")
    raw = _build_email(ical)
    result = ImipParser.parse(raw)
    assert result.method == ImipMethod.CANCEL


def test_parse_extracts_from_and_to():
    ical = _serializer.build_imip(_make_event(), "REQUEST")
    raw = _build_email(ical, from_addr="organizer@example.com", to_addr="attendee@example.com")
    result = ImipParser.parse(raw)
    assert result.from_email == "organizer@example.com"
    assert "attendee@example.com" in result.to_emails


def test_parse_extracts_event_uid():
    ical = _serializer.build_imip(_make_event(), "REQUEST")
    raw = _build_email(ical)
    result = ImipParser.parse(raw)
    assert result.event.uid == "test-uid@example.com"


def test_parse_no_calendar_part_raises():
    msg = MIMEMultipart()
    msg["From"] = "a@example.com"
    msg["To"] = "b@example.com"
    msg.attach(MIMEText("plain text body", "plain"))
    with pytest.raises(RequestException) as exc_info:
        ImipParser.parse(msg.as_bytes())
    assert exc_info.value.error == ERROR_CALENDAR_ICS_PARSE_FAILED


def test_parse_missing_method_raises():
    # Build iCal without METHOD property
    ical_no_method = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test@example.com\r\n"
        "SUMMARY:Test\r\n"
        "DTSTART:20260601T090000Z\r\n"
        "DTEND:20260601T100000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    raw = _build_email(ical_no_method)
    with pytest.raises(RequestException) as exc_info:
        ImipParser.parse(raw)
    assert exc_info.value.error == ERROR_CALENDAR_IMIP_INVALID_REQUEST


def test_parse_unknown_method_raises():
    ical_bad_method = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Test//EN\r\n"
        "METHOD:BADMETHOD\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test@example.com\r\n"
        "SUMMARY:Test\r\n"
        "DTSTART:20260601T090000Z\r\n"
        "DTEND:20260601T100000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    raw = _build_email(ical_bad_method)
    with pytest.raises(RequestException) as exc_info:
        ImipParser.parse(raw)
    assert exc_info.value.error == ERROR_CALENDAR_IMIP_INVALID_REQUEST


def test_parse_stores_ical_content():
    ical = _serializer.build_imip(_make_event(), "REQUEST")
    raw = _build_email(ical)
    result = ImipParser.parse(raw)
    assert "METHOD:REQUEST" in result.ical_content
    assert "BEGIN:VCALENDAR" in result.ical_content


# ========== Tests for ImipParser.detect_method (non-raising) ==========

def test_detect_method_request():
    ical = _serializer.build_imip(_make_event(), "REQUEST")
    assert ImipParser.detect_method(ical.encode("utf-8")) == ImipMethod.REQUEST


def test_detect_method_reply_and_cancel():
    reply = _serializer.build_imip(_make_event(), "REPLY")
    cancel = _serializer.build_imip(_make_event(), "CANCEL")
    assert ImipParser.detect_method(reply.encode("utf-8")) == ImipMethod.REPLY
    assert ImipParser.detect_method(cancel.encode("utf-8")) == ImipMethod.CANCEL


def test_detect_method_none_when_no_method():
    plain = _serializer.serialize(_make_event())  # a VEVENT export, no METHOD property
    assert ImipParser.detect_method(plain.encode("utf-8")) is None


def test_detect_method_none_when_unsupported():
    ical = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:PUBLISH\r\nEND:VCALENDAR\r\n"
    assert ImipParser.detect_method(ical.encode("utf-8")) is None


def test_detect_method_none_on_malformed_payload():
    # Not a VCALENDAR at all - the lib parse must not raise, just yield None.
    assert ImipParser.detect_method(b"this is not an icalendar document") is None
