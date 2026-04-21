"""
Unit tests for CalendarEventsDeserializerJson.
Verifies that a JSON array of events is correctly parsed into a list of CalEvent objects.
"""
import json

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventsDeserializerJson import CalendarEventsDeserializerJson

EVENT_1 = {
    "uid": "evt1@example.com",
    "title": "Standup",
    "date_start": "2026-03-19T09:30:00.000Z",
    "date_end": "2026-03-19T10:00:00.000Z",
}
EVENT_2 = {
    "uid": "evt2@example.com",
    "title": "Review",
    "date_start": "2026-03-20T14:00:00.000Z",
    "date_end": "2026-03-20T15:00:00.000Z",
}

JSON_ARRAY = json.dumps([EVENT_1, EVENT_2])
JSON_WRAPPED = json.dumps({"events": [EVENT_1, EVENT_2]})
JSON_EMPTY_ARRAY = json.dumps([])
JSON_EMPTY_WRAPPED = json.dumps({"events": []})


@pytest.fixture
def deserializer():
    return CalendarEventsDeserializerJson()


def test_returns_list(deserializer):
    assert isinstance(deserializer.deserialize(JSON_ARRAY), list)


def test_array_count(deserializer):
    assert len(deserializer.deserialize(JSON_ARRAY)) == 2


def test_wrapped_count(deserializer):
    assert len(deserializer.deserialize(JSON_WRAPPED)) == 2


def test_array_uids(deserializer):
    events = deserializer.deserialize(JSON_ARRAY)
    assert events[0].uid == "evt1@example.com"
    assert events[1].uid == "evt2@example.com"


def test_wrapped_uids(deserializer):
    events = deserializer.deserialize(JSON_WRAPPED)
    assert events[0].uid == "evt1@example.com"


def test_empty_array(deserializer):
    assert deserializer.deserialize(JSON_EMPTY_ARRAY) == []


def test_empty_wrapped(deserializer):
    assert deserializer.deserialize(JSON_EMPTY_WRAPPED) == []


def test_from_list(deserializer):
    events = deserializer.from_list([EVENT_1])
    assert len(events) == 1
    assert isinstance(events[0], CalEvent)


def test_roundtrip(deserializer):
    from app.module.calendar.serializer.CalendarEventsSerializerJson import CalendarEventsSerializerJson
    serializer = CalendarEventsSerializerJson()
    events_in = deserializer.deserialize(JSON_ARRAY)
    output = serializer.serialize(events_in)
    events_out = deserializer.deserialize(output)
    assert len(events_out) == len(events_in)
    assert events_out[0].uid == events_in[0].uid
    assert events_out[1].uid == events_in[1].uid
