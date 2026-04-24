"""
Unit tests for CalendarEventSerializerDict.
Verifies that CalEvent objects are correctly serialized to the SOGo6 REST API schema.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RelationType import RelationType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.serializer.CalendarEventSerializerDict import CalendarEventSerializerDict

_UTC = timezone.utc


@pytest.fixture
def serializer():
    return CalendarEventSerializerDict()


@pytest.fixture
def minimal_event():
    return CalEvent(
        uid="evt@example.com",
        title="Standup",
        date_start=datetime(2026, 3, 19, 9, 30, tzinfo=_UTC),
        date_end=datetime(2026, 3, 19, 10, 0, tzinfo=_UTC),
    )


def test_dates_are_iso_utc_with_milliseconds(serializer, minimal_event):
    d = serializer.serialize(minimal_event)
    assert d["date_start"] == "2026-03-19T09:30:00.000Z"
    assert d["date_end"] == "2026-03-19T10:00:00.000Z"


def test_microseconds_truncated_to_milliseconds(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, 12, 0, 0, 500123, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 13, tzinfo=_UTC),
    )
    assert serializer.serialize(event)["date_start"] == "2026-01-01T12:00:00.500Z"


def test_enums_serialized_as_lowercase_strings(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        status=EventStatus.CANCELLED,
        visibility=EventVisibility.PRIVATE,
        show_as=ShowAs.OUT_OF_OFFICE,
    )
    d = serializer.serialize(event)
    assert d["status"] == "cancelled"
    assert d["visibility"] == "private"
    assert d["show_as"] == "out-of-office"


def test_optional_fields_null_or_empty_when_absent(serializer, minimal_event):
    d = serializer.serialize(minimal_event)
    assert d["description"] is None
    assert d["url"] is None
    assert d["color"] is None
    assert d["organizer"] is None
    assert d["conference_data"] is None
    assert d["created_at"] is None
    assert d["attendees"] == []
    assert d["reminders"] == []
    assert d["attachments"] == []
    assert d["categories"] == []
    assert d["related_to"] == []
    assert d["extra_properties"] == {}


def test_organizer_all_fields(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        organizer=CalOrganizer(
            email="manager@example.com", name="Sarah",
            role=AttendeeRole.CHAIR, status=AttendeeStatus.ACCEPTED,
            sent_by="proxy@example.com", dir_ref="ldap://example.com/cn=Sarah",
        ),
    )
    org = serializer.serialize(event)["organizer"]
    assert org["email"] == "manager@example.com"
    assert org["role"] == "chair"
    assert org["status"] == "accepted"
    assert org["sent_by"] == "proxy@example.com"
    assert org["dir_ref"] == "ldap://example.com/cn=Sarah"


def test_attendee_all_fields(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        attendees=[CalAttendee(
            email="room@example.com", name="Room A",
            role=AttendeeRole.NON_PARTICIPANT, status=AttendeeStatus.ACCEPTED,
            rsvp=False, cutype=CalUserType.ROOM,
            delegated_from="alice@example.com", delegated_to="bob@example.com",
            sent_by="proxy@example.com", dir_ref="ldap://example.com/cn=Room",
        )],
    )
    att = serializer.serialize(event)["attendees"][0]
    assert att["role"] == "non-participant"
    assert att["cutype"] == "room"
    assert att["delegated_from"] == "alice@example.com"
    assert att["delegated_to"] == "bob@example.com"
    assert att["sent_by"] == "proxy@example.com"
    assert att["dir_ref"] == "ldap://example.com/cn=Room"


def test_related_to(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        related_to=[CalEventRelation(uid="parent@example.com", relation_type=RelationType.PARENT)],
    )
    rels = serializer.serialize(event)["related_to"]
    assert rels[0] == {"uid": "parent@example.com", "relation_type": "parent"}


def test_extra_properties(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        extra_properties={"X-CUSTOM-FIELD": "value"},
    )
    assert serializer.serialize(event)["extra_properties"] == {"X-CUSTOM-FIELD": "value"}


def test_reminders(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        reminders=[
            CalReminder(method=ReminderMethod.POPUP, minutes_before=15),
            CalReminder(method=ReminderMethod.EMAIL, minutes_before=60),
        ],
    )
    rems = serializer.serialize(event)["reminders"]
    assert rems[0] == {"method": "popup", "minutes_before": 15}
    assert rems[1] == {"method": "email", "minutes_before": 60}


# ==========================================================================
# VTODO fields
# ==========================================================================

def test_component_type_task(serializer):
    event = CalEvent(
        uid="t@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 31, tzinfo=_UTC),
        component_type=ComponentType.TASK,
    )
    assert serializer.serialize(event)["component_type"] == "task"


def test_percent_complete_value(serializer):
    event = CalEvent(
        uid="t@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 31, tzinfo=_UTC),
        component_type=ComponentType.TASK,
        percent_complete=60,
    )
    assert serializer.serialize(event)["percent_complete"] == 60


def test_completed_at_serialized(serializer):
    event = CalEvent(
        uid="t@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 31, tzinfo=_UTC),
        component_type=ComponentType.TASK,
        completed_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=_UTC),
    )
    assert serializer.serialize(event)["completed_at"] == "2026-01-15T12:00:00.000Z"


# ========== Recurrence fields ==========

def test_recurrence_rule_serialized():
    event = CalEvent(
        uid="r@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        recurrence_rule=CalRecurrenceRule(
            frequency=RecurrenceFrequency.WEEKLY,
            interval=2,
            by_day=["MO", "FR"],
            count=5,
        ),
    )
    rule = CalendarEventSerializerDict().serialize(event)["recurrence_rule"]
    assert rule["frequency"] == "weekly"
    assert rule["interval"] == 2
    assert rule["by_day"] == ["MO", "FR"]
    assert rule["count"] == 5
    assert rule["until"] is None


def test_recurrence_exceptions_serialized():
    event = CalEvent(
        uid="r@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        recurrence_exceptions=[
            datetime(2026, 3, 7, 9, 0, 0, tzinfo=_UTC),
            datetime(2026, 3, 14, 9, 0, 0, tzinfo=_UTC),
        ],
    )
    exceptions = CalendarEventSerializerDict().serialize(event)["recurrence_exceptions"]
    assert exceptions == ["2026-03-07T09:00:00.000Z", "2026-03-14T09:00:00.000Z"]


def test_recurrence_id_serialized():
    event = CalEvent(
        uid="r@e.com", title="T",
        date_start=datetime(2026, 3, 7, 9, 0, 0, tzinfo=_UTC),
        date_end=datetime(2026, 3, 7, 10, 0, 0, tzinfo=_UTC),
        recurrence_id=datetime(2026, 3, 7, 9, 0, 0, tzinfo=_UTC),
    )
    assert CalendarEventSerializerDict().serialize(event)["recurrence_id"] == "2026-03-07T09:00:00.000Z"


# ========== dates_with_tz ==========

def test_dates_with_tz_event_timezone(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 6, 10, 9, 0, tzinfo=_UTC),
        date_end=datetime(2026, 6, 10, 10, 0, tzinfo=_UTC),
        timezone="Europe/Paris",
    )
    d = serializer.serialize(event)["dates_with_tz"]
    # Europe/Paris in summer = UTC+2
    assert d["date_start_tz_event"] == "2026-06-10T11:00:00+02:00"
    assert d["date_end_tz_event"] == "2026-06-10T12:00:00+02:00"
    assert d["date_start_tz_calendar"] is None
    assert d["date_end_tz_calendar"] is None


def test_dates_with_tz_calendar_timezone(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 15, 8, 0, tzinfo=_UTC),
        date_end=datetime(2026, 1, 15, 9, 0, tzinfo=_UTC),
        timezone="UTC",
        calendar_timezone="America/New_York",
    )
    d = serializer.serialize(event)["dates_with_tz"]
    # America/New_York in winter = UTC-5
    assert d["date_start_tz_calendar"] == "2026-01-15T03:00:00-05:00"
    assert d["date_end_tz_calendar"] == "2026-01-15T04:00:00-05:00"


def test_dates_with_tz_both_timezones(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 6, 10, 9, 0, tzinfo=_UTC),
        date_end=datetime(2026, 6, 10, 10, 0, tzinfo=_UTC),
        timezone="Europe/Paris",
        calendar_timezone="America/New_York",
    )
    d = serializer.serialize(event)["dates_with_tz"]
    assert d["date_start_tz_event"] == "2026-06-10T11:00:00+02:00"
    assert d["date_start_tz_calendar"] == "2026-06-10T05:00:00-04:00"


def test_dates_with_tz_unknown_timezone_returns_none(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        timezone="Not/ATimezone",
    )
    d = serializer.serialize(event)["dates_with_tz"]
    assert d["date_start_tz_event"] is None
    assert d["date_end_tz_event"] is None


def test_dates_with_tz_no_timezone_all_none(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        timezone="",
    )
    d = serializer.serialize(event)["dates_with_tz"]
    assert all(v is None for v in d.values())


def test_conference_data_and_attachment(serializer):
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        conference_data=CalConferenceData(
            type="zoom", url="https://zoom.us/j/123", conference_id="123",
            entry_points=[CalConferenceEntryPoint(type="video", uri="https://zoom.us/j/123", label="Zoom")],
        ),
        attachments=[CalAttachment(filename="report.pdf", mime_type="application/pdf", url="https://s.example.com/r.pdf", size=1024)],
    )
    d = serializer.serialize(event)
    assert d["conference_data"]["type"] == "zoom"
    assert d["conference_data"]["entry_points"][0]["label"] == "Zoom"
    assert d["attachments"][0]["filename"] == "report.pdf"
