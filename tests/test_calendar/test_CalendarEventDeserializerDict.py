"""
Unit tests for CalEventDeserializerDict.
Verifies that dict payloads matching the SOGo6 REST API schema are correctly parsed into CalEvent objects.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.module.calendar.model.CalEvent import CalEvent

FULL_EVENT = {
    "key": "evt_001",
    "calendar_key": "7f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
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
    return CalEventDeserializerDict()


def test_full_event_scalar_fields(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert event.key == "evt_001"
    assert event.calendar_key == "7f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"
    assert event.uid == "evt_001@sogo.example.com"
    assert event.title == "Team Standup"
    assert event.description == "Daily team sync meeting"
    assert event.location == "Conference Room A"
    assert event.timezone == "Europe/Paris"
    assert event.sequence == 2
    assert event.all_day is False


def test_dates_are_utc_aware(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert event.date_start == datetime(2026, 3, 19, 9, 30, tzinfo=timezone.utc)
    assert event.date_end == datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc)
    # created_at/updated_at are server-managed and not read from user input
    assert event.created_at is None


def test_enums_parsed(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert event.status == EventStatus.CONFIRMED
    assert event.show_as == ShowAs.BUSY


def test_organizer(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert event.organizer.email == "manager@example.com"
    assert event.organizer.role == AttendeeRole.CHAIR
    assert event.organizer.status == AttendeeStatus.ACCEPTED


def test_attendees(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert len(event.attendees) == 2
    assert event.attendees[0].role == AttendeeRole.REQUIRED
    assert event.attendees[1].role == AttendeeRole.OPTIONAL


def test_reminders(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert len(event.reminders) == 2
    assert event.reminders[0].minutes_before == 15
    assert event.reminders[1].minutes_before == 60


def test_reminder_without_offset_left_unresolved(deserializer):
    # No minutes_before: the deserializer leaves None so the module can apply the calendar default.
    event = deserializer.deserialize({"date_start": "2026-03-19T09:30:00.000Z",
                                      "reminders": [{"method": "popup"}]})
    assert event.reminders[0].minutes_before is None


def test_visibility_omitted_left_undefined(deserializer):
    # No visibility: left UNDEFINED so the module can apply the calendar default_type.
    event = deserializer.deserialize({"date_start": "2026-03-19T09:30:00.000Z"})
    assert event.visibility == EventVisibility.UNDEFINED


def test_conference_data_and_attachments(deserializer):
    event = deserializer.deserialize(FULL_EVENT)
    assert event.conference_data.type == "zoom"
    assert len(event.conference_data.entry_points) == 1
    assert event.attachments[0].filename == "Q3.pdf"


def test_minimal_event_optional_fields_absent(deserializer):
    event = deserializer.deserialize(MINIMAL_EVENT)
    assert event.key is None
    assert event.organizer is None
    assert event.attendees == []
    assert event.reminders == []
    assert event.conference_data is None
    assert event.created_at is None


def test_unknown_enum_falls_back_to_default(deserializer):
    data = {**MINIMAL_EVENT, "status": "unknown-value"}
    assert deserializer.deserialize(data).status == EventStatus.CONFIRMED



# ==========================================================================
# VTODO fields
# ==========================================================================

def test_component_type_defaults_to_event(deserializer):
    event = deserializer.deserialize(MINIMAL_EVENT)
    assert event.component_type == ComponentType.EVENT


def test_component_type_task(deserializer):
    data = {**MINIMAL_EVENT, "component_type": "task"}
    assert deserializer.deserialize(data).component_type == ComponentType.TASK


def test_percent_complete_parsed(deserializer):
    data = {**MINIMAL_EVENT, "component_type": "task", "percent_complete": 80}
    assert deserializer.deserialize(data).percent_complete == 80


def test_completed_at_parsed(deserializer):
    data = {**MINIMAL_EVENT, "completed_at": "2026-01-15T12:00:00.000Z"}
    event = deserializer.deserialize(data)
    assert event.completed_at == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ==========================================================================
# New fields: url, categories, related_to, extra_properties, recurrence
# ==========================================================================

def test_url_parsed(deserializer):
    data = {**MINIMAL_EVENT, "url": "https://example.com/event"}
    assert deserializer.deserialize(data).url == "https://example.com/event"


def test_categories_parsed(deserializer):
    data = {**MINIMAL_EVENT, "categories": ["work", "meeting"]}
    assert deserializer.deserialize(data).categories == ["work", "meeting"]


def test_extra_properties_parsed(deserializer):
    data = {**MINIMAL_EVENT, "extra_properties": {"X-CUSTOM": "value"}}
    assert deserializer.deserialize(data).extra_properties == {"X-CUSTOM": "value"}


def test_related_to_parsed(deserializer):
    data = {**MINIMAL_EVENT, "related_to": [{"uid": "parent@example.com", "relation_type": "parent"}]}
    relations = deserializer.deserialize(data).related_to
    assert len(relations) == 1
    assert relations[0].uid == "parent@example.com"


def test_recurrence_rule_absent_is_none(deserializer):
    assert deserializer.deserialize(MINIMAL_EVENT).recurrence_rule is None


def test_recurrence_rule_parsed(deserializer):
    data = {**MINIMAL_EVENT, "recurrence_rule": {
        "frequency": "weekly",
        "interval": 2,
        "by_day": ["MO", "FR"],
        "count": 5,
    }}
    rule = deserializer.deserialize(data).recurrence_rule
    assert rule is not None
    assert rule.frequency.value == "weekly"
    assert rule.interval == 2
    assert rule.count == 5
    assert rule.by_day == ["MO", "FR"]


def test_recurrence_exceptions_parsed(deserializer):
    data = {**MINIMAL_EVENT, "recurrence_exceptions": ["2026-03-07T09:00:00.000Z"]}
    exceptions = deserializer.deserialize(data).recurrence_exceptions
    assert len(exceptions) == 1
    assert exceptions[0] == datetime(2026, 3, 7, 9, 0, 0, tzinfo=timezone.utc)


def test_recurrence_id_parsed(deserializer):
    data = {**MINIMAL_EVENT, "recurrence_id": "2026-03-07T09:00:00.000Z"}
    assert deserializer.deserialize(data).recurrence_id == datetime(2026, 3, 7, 9, 0, 0, tzinfo=timezone.utc)


def test_recurrence_roundtrip():
    """Serialize then deserialize a recurring event and verify lossless round-trip."""
    event = CalEvent(
        uid="r@example.com",
        title="Weekly sync",
        date_start=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
        date_end=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
        recurrence_rule=CalRecurrenceRule(
            frequency=RecurrenceFrequency.WEEKLY,
            interval=1,
            by_day=["MO"],
            count=10,
        ),
        recurrence_exceptions=[datetime(2026, 3, 9, 9, 0, 0, tzinfo=timezone.utc)],
    )

    blob = CalEventSerializerDict().serialize(event)
    restored = CalEventDeserializerDict().deserialize(blob)

    assert restored.recurrence_rule.frequency.value == "weekly"
    assert restored.recurrence_rule.by_day == ["MO"]
    assert restored.recurrence_rule.count == 10
    assert len(restored.recurrence_exceptions) == 1


# ==========================================================================
# deserialize - partial dict (update scenario)
# ==========================================================================

def test_partial_recurrence_exceptions_as_datetimes(deserializer):
    """recurrence_exceptions strings must be parsed to datetime objects."""
    event = deserializer.deserialize({"recurrence_exceptions": ["2026-06-03T07:00:00Z"]})
    assert len(event.recurrence_exceptions) == 1
    assert isinstance(event.recurrence_exceptions[0], datetime)
    assert event.recurrence_exceptions[0] == datetime(2026, 6, 3, 7, 0, 0, tzinfo=timezone.utc)


def test_partial_recurrence_rule_parsed(deserializer):
    event = deserializer.deserialize({
        "recurrence_rule": {"frequency": "weekly", "interval": 2, "count": 4}
    })
    assert event.recurrence_rule is not None
    assert event.recurrence_rule.frequency.value == "weekly"
    assert event.recurrence_rule.interval == 2
    assert event.recurrence_rule.count == 4


def test_partial_recurrence_rule_none_preserved(deserializer):
    event = deserializer.deserialize({"recurrence_rule": None})
    assert event.recurrence_rule is None


def test_partial_scalar_fields(deserializer):
    event = deserializer.deserialize({"title": "New title", "sequence": 3})
    assert event.title == "New title"
    assert event.sequence == 3


def test_partial_attendees_parsed(deserializer):
    event = deserializer.deserialize({
        "attendees": [{"email": "bob@example.org", "name": "Bob", "role": "required",
                       "status": "needs-action", "rsvp": True, "cutype": "individual"}]
    })
    assert len(event.attendees) == 1
    assert event.attendees[0].role == AttendeeRole.REQUIRED


def test_partial_date_fields_none_when_missing(deserializer):
    """When date_start/date_end are not in the dict, they are None."""
    event = deserializer.deserialize({"title": "X"})
    assert event.date_start is None
    assert event.date_end is None
