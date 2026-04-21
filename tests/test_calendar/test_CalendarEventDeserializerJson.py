"""
Unit tests for CalendarEventDeserializerJson.
Verifies that JSON payloads matching the SOGo6 REST API schema are correctly parsed into CalEvent objects.
"""
import json
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson

FULL_EVENT = {
    "id": "evt_001",
    "calendar_id": 42,
    "uid": "evt_001@sogo.example.com",
    "title": "Team Standup",
    "description": "Daily team sync meeting",
    "location": "Conference Room A",
    "date_start": "2026-03-19T09:30:00.000Z",
    "date_end": "2026-03-19T10:00:00.000Z",
    "all_day": False,
    "timezone": "Europe/Paris",
    "status": "confirmed",
    "visibility": "public",
    "show_as": "busy",
    "color": "#4285f4",
    "sequence": 2,
    "organizer": {
        "email": "manager@example.com",
        "name": "Sarah Manager",
        "role": "chair",
        "status": "accepted",
    },
    "attendees": [
        {"email": "john.doe@example.com", "name": "John Doe", "role": "required", "status": "accepted", "rsvp": True},
        {"email": "bob@example.com", "name": "Bob", "role": "optional", "status": "needs-action", "rsvp": False},
    ],
    "reminders": [
        {"method": "popup", "minutes_before": 15},
        {"method": "email", "minutes_before": 60},
    ],
    "conference_data": {
        "type": "zoom",
        "url": "https://zoom.us/j/123",
        "conference_id": "123-456",
        "entry_points": [
            {"type": "video", "uri": "https://zoom.us/j/123", "label": "Zoom Meeting"},
        ],
    },
    "attachments": [
        {"filename": "Q3.pdf", "mime_type": "application/pdf", "url": "https://s.example.com/Q3.pdf", "size": 2048},
    ],
    "created_at": "2026-03-12T07:53:38.581Z",
    "updated_at": "2026-03-17T07:53:38.581Z",
}

MINIMAL_EVENT = {
    "uid": "min@example.com",
    "title": "Minimal Event",
    "date_start": "2026-01-01T00:00:00.000Z",
    "date_end": "2026-01-01T01:00:00.000Z",
}


@pytest.fixture
def deserializer():
    return CalendarEventDeserializerJson()


def test_full_event_scalar_fields(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert event.id == "evt_001"
    assert event.calendar_id == 42
    assert event.uid == "evt_001@sogo.example.com"
    assert event.title == "Team Standup"
    assert event.description == "Daily team sync meeting"
    assert event.location == "Conference Room A"
    assert event.timezone == "Europe/Paris"
    assert event.sequence == 2
    assert event.all_day is False


def test_dates_are_utc_aware(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert event.date_start == datetime(2026, 3, 19, 9, 30, tzinfo=timezone.utc)
    assert event.date_end == datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc)
    assert event.created_at == datetime(2026, 3, 12, 7, 53, 38, 581000, tzinfo=timezone.utc)


def test_enums_parsed(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert event.status == EventStatus.CONFIRMED
    assert event.show_as == ShowAs.BUSY


def test_organizer(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert event.organizer.email == "manager@example.com"
    assert event.organizer.role == AttendeeRole.CHAIR
    assert event.organizer.status == AttendeeStatus.ACCEPTED


def test_attendees(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert len(event.attendees) == 2
    assert event.attendees[0].role == AttendeeRole.REQUIRED
    assert event.attendees[1].role == AttendeeRole.OPTIONAL


def test_reminders(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert len(event.reminders) == 2
    assert event.reminders[0].minutes_before == 15
    assert event.reminders[1].minutes_before == 60


def test_conference_data_and_attachments(deserializer):
    event = deserializer.from_dict(FULL_EVENT)
    assert event.conference_data.type == "zoom"
    assert len(event.conference_data.entry_points) == 1
    assert event.attachments[0].filename == "Q3.pdf"


def test_minimal_event_optional_fields_absent(deserializer):
    event = deserializer.from_dict(MINIMAL_EVENT)
    assert event.id is None
    assert event.organizer is None
    assert event.attendees == []
    assert event.reminders == []
    assert event.conference_data is None
    assert event.created_at is None


def test_unknown_enum_falls_back_to_default(deserializer):
    data = {**MINIMAL_EVENT, "status": "unknown-value"}
    assert deserializer.from_dict(data).status == EventStatus.CONFIRMED


def test_from_dict_and_deserialize_are_equivalent(deserializer):
    via_dict = deserializer.from_dict(FULL_EVENT)
    via_str = deserializer.deserialize(json.dumps(FULL_EVENT))
    assert via_dict.uid == via_str.uid
    assert via_dict.date_start == via_str.date_start


# ==========================================================================
# VTODO fields
# ==========================================================================

def test_component_type_defaults_to_event(deserializer):
    event = deserializer.from_dict(MINIMAL_EVENT)
    assert event.component_type == ComponentType.EVENT


def test_component_type_task(deserializer):
    data = {**MINIMAL_EVENT, "component_type": "task"}
    assert deserializer.from_dict(data).component_type == ComponentType.TASK


def test_percent_complete_absent_is_none(deserializer):
    assert deserializer.from_dict(MINIMAL_EVENT).percent_complete is None


def test_percent_complete_parsed(deserializer):
    data = {**MINIMAL_EVENT, "component_type": "task", "percent_complete": 80}
    assert deserializer.from_dict(data).percent_complete == 80


def test_completed_at_absent_is_none(deserializer):
    assert deserializer.from_dict(MINIMAL_EVENT).completed_at is None


def test_completed_at_parsed(deserializer):
    data = {**MINIMAL_EVENT, "completed_at": "2026-01-15T12:00:00.000Z"}
    event = deserializer.from_dict(data)
    assert event.completed_at == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
