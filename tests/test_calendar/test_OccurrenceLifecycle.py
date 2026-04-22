"""
Tests for detached occurrence lifecycle.

Detached occurrences are regular CalEvents with recurrence_id set that override
a specific instance of a recurring series. They flow through existing endpoints:
- POST /calendars/{key}/events with recurrence_id → create_event → insert_event detects recurrence_id
- DELETE /events/{key} on an occurrence → delete_event → delete_detached_occurrence
- PATCH /events/{master_key} with recurrence_exceptions → cancel via EXDATE without detaching
"""
from datetime import datetime, timezone

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson
from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson

_UTC = timezone.utc


# ========== Serializer / deserializer ==========

def test_serializer_includes_parent_uid():
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
        parent_uid="master@example.com",
    )
    assert CalendarEventSerializerJson().to_dict(event)["parent_uid"] == "master@example.com"


def test_serializer_parent_uid_null_when_absent():
    event = CalEvent(
        uid="u@e.com", title="T",
        date_start=datetime(2026, 1, 1, tzinfo=_UTC),
        date_end=datetime(2026, 1, 1, 1, tzinfo=_UTC),
    )
    assert CalendarEventSerializerJson().to_dict(event)["parent_uid"] is None


def test_deserializer_parses_parent_uid():
    data = {
        "uid": "u@e.com", "title": "T",
        "date_start": "2026-01-01T00:00:00.000Z",
        "date_end": "2026-01-01T01:00:00.000Z",
        "parent_uid": "master@example.com",
    }
    assert CalendarEventDeserializerJson().from_dict(data).parent_uid == "master@example.com"


def test_deserializer_parent_uid_absent_is_none():
    data = {
        "uid": "u@e.com", "title": "T",
        "date_start": "2026-01-01T00:00:00.000Z",
        "date_end": "2026-01-01T01:00:00.000Z",
    }
    assert CalendarEventDeserializerJson().from_dict(data).parent_uid is None


# ========== Serializer round-trip ==========

def test_occurrence_roundtrip_preserves_parent_uid():
    rid = datetime(2026, 3, 9, 9, 0, tzinfo=_UTC)
    occ = CalEvent(
        uid="master@example.com", title="Modified sync",
        date_start=rid, date_end=rid.replace(hour=11),
        recurrence_id=rid, parent_uid="master@example.com",
    )
    blob = CalendarEventSerializerJson().to_dict(occ)
    restored = CalendarEventDeserializerJson().from_dict(blob)
    assert restored.parent_uid == "master@example.com"
    assert restored.recurrence_id == rid
    assert restored.recurrence_rule is None
