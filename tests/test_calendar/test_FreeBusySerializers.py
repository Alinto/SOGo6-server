"""Tests for FreeBusy serializers and deserializers (Dict and iCal)."""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.serializer.FreeBusyDeserializerDict import FreeBusyDeserializerDict
from app.module.calendar.serializer.FreeBusyDeserializerIcal import FreeBusyDeserializerIcal
from app.module.calendar.serializer.FreeBusySerializerDict import FreeBusySerializerDict
from app.module.calendar.serializer.FreeBusySerializerIcal import FreeBusySerializerIcal
from app.utils.exceptions import RequestException

_UTC = timezone.utc
_START = datetime(2026, 6, 15, 14, 0, tzinfo=_UTC)
_END   = datetime(2026, 6, 15, 15, 0, tzinfo=_UTC)
_RANGE_START = datetime(2026, 6, 15, 0, 0, tzinfo=_UTC)
_RANGE_END   = datetime(2026, 6, 16, 0, 0, tzinfo=_UTC)

_ICAL_REPLY = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REPLY\r\n"
    "BEGIN:VFREEBUSY\r\n"
    "DTSTART:20260615T000000Z\r\nDTEND:20260616T000000Z\r\n"
    "FREEBUSY;FBTYPE=BUSY:20260615T140000Z/20260615T150000Z\r\n"
    "END:VFREEBUSY\r\nEND:VCALENDAR\r\n"
)

_ICAL_REQUEST = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REQUEST\r\n"
    "BEGIN:VFREEBUSY\r\n"
    "DTSTART:20260615T000000Z\r\nDTEND:20260616T000000Z\r\n"
    "ATTENDEE:mailto:user1@example.com\r\n"
    "ATTENDEE:mailto:user2@example.com\r\n"
    "ORGANIZER:mailto:org@example.com\r\n"
    "END:VFREEBUSY\r\nEND:VCALENDAR\r\n"
)


# ========== FreeBusySerializerDict ==========

def test_dict_serialize_basic():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert result["attendees"]["u@x"]["periods"][0]["type"] == FreeBusyType.BUSY.value


def test_dict_title_present_when_set():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY, title="Meeting")
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert result["attendees"]["u@x"]["periods"][0]["title"] == "Meeting"


def test_dict_title_absent_when_none():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY, title=None)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert "title" not in result["attendees"]["u@x"]["periods"][0]


def test_is_available_always_present():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.TENTATIVE)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert "is_available" in result


def test_is_available_true_when_no_busy():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.TENTATIVE)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert result["is_available"] is True


def test_is_available_false_when_busy():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert result["is_available"] is False


def test_is_available_false_when_unavailable():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.UNAVAILABLE)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": [period]}, _RANGE_START, _RANGE_END))
    assert result["is_available"] is False


def test_is_available_false_when_one_attendee_busy():
    busy = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    result = FreeBusySerializerDict().serialize(CalFreeBusyResult({"a@x": [], "b@x": [busy]}, _RANGE_START, _RANGE_END))
    assert result["is_available"] is False


# ========== FreeBusySerializerIcal ==========

def test_ical_method_reply():
    ical = FreeBusySerializerIcal().serialize(CalFreeBusyResult({}, _RANGE_START, _RANGE_END))
    assert "METHOD:REPLY" in ical


def test_ical_attendee_present():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    ical = FreeBusySerializerIcal().serialize(CalFreeBusyResult({"user@x.com": [period]}, _RANGE_START, _RANGE_END))
    assert "ATTENDEE" in ical
    assert "user@x.com" in ical


def test_ical_freebusy_property_present():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    ical = FreeBusySerializerIcal().serialize(CalFreeBusyResult({"user@x.com": [period]}, _RANGE_START, _RANGE_END))
    assert "FREEBUSY" in ical


def test_ical_two_vfreebusy_for_two_attendees():
    period = CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY)
    ical = FreeBusySerializerIcal().serialize(CalFreeBusyResult(
        {"a@x.com": [period], "b@x.com": [period]},
        _RANGE_START,
        _RANGE_END,
    ))
    assert ical.count("BEGIN:VFREEBUSY") == 2


# ========== FreeBusyDeserializerIcal.parse_reply ==========

def test_ical_parse_reply():
    periods = FreeBusyDeserializerIcal().parse_reply(_ICAL_REPLY)
    assert len(periods) == 1
    assert periods[0].fb_type == FreeBusyType.BUSY
    assert periods[0].date_start == _START
    assert periods[0].date_end == _END


# ========== FreeBusyDeserializerIcal.deserialize ==========

def test_ical_deserialize_request_attendees():
    req = FreeBusyDeserializerIcal().deserialize(_ICAL_REQUEST)
    assert "user1@example.com" in req.attendees
    assert "user2@example.com" in req.attendees


def test_ical_deserialize_request_organizer():
    req = FreeBusyDeserializerIcal().deserialize(_ICAL_REQUEST)
    assert req.organizer == "org@example.com"


def test_ical_deserialize_request_dates():
    req = FreeBusyDeserializerIcal().deserialize(_ICAL_REQUEST)
    assert req.start == datetime(2026, 6, 15, 0, 0, tzinfo=_UTC)
    assert req.end   == datetime(2026, 6, 16, 0, 0, tzinfo=_UTC)


def test_ical_deserialize_request_invalid():
    with pytest.raises(RequestException):
        FreeBusyDeserializerIcal().deserialize("NOT ICAL")




# ========== Round-trip ==========

def test_dict_roundtrip():
    periods = [
        CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY, title="Meeting"),
        CalFreeBusyPeriod(datetime(2026, 6, 15, 16, 0, tzinfo=_UTC), datetime(2026, 6, 15, 17, 0, tzinfo=_UTC), FreeBusyType.TENTATIVE),
    ]
    serialized = FreeBusySerializerDict().serialize(CalFreeBusyResult({"u@x": periods}, _RANGE_START, _RANGE_END))
    restored = FreeBusyDeserializerDict().deserialize(serialized)
    assert len(restored["u@x"]) == 2
    assert restored["u@x"][0].date_start == _START
    assert restored["u@x"][0].date_end == _END
    assert restored["u@x"][0].fb_type == FreeBusyType.BUSY
    assert restored["u@x"][0].title == "Meeting"
    assert restored["u@x"][1].fb_type == FreeBusyType.TENTATIVE


def test_ical_roundtrip():
    # iCal VFREEBUSY merges all periods into a flat list without attendee separation.
    # Titles are not preserved in RFC 5545 FREEBUSY properties.
    periods = [
        CalFreeBusyPeriod(_START, _END, FreeBusyType.BUSY),
        CalFreeBusyPeriod(datetime(2026, 6, 15, 16, 0, tzinfo=_UTC), datetime(2026, 6, 15, 17, 0, tzinfo=_UTC), FreeBusyType.TENTATIVE),
    ]
    serialized = FreeBusySerializerIcal().serialize(CalFreeBusyResult({"u@x": periods}, _RANGE_START, _RANGE_END))
    restored = FreeBusyDeserializerIcal().parse_reply(serialized)
    assert len(restored) == 2
    types = {p.fb_type for p in restored}
    assert FreeBusyType.BUSY in types
    assert FreeBusyType.TENTATIVE in types
    starts = {p.date_start for p in restored}
    assert _START in starts
