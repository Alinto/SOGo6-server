"""
Unit tests for CalendarEventsDeserializerDict.
"""
from app.module.calendar.serializer.CalendarEventsDeserializerDict import CalendarEventsDeserializerDict
from app.module.calendar.serializer.CalendarEventsSerializerDict import CalendarEventsSerializerDict

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


def test_deserialize_uids():
    deserializer = CalendarEventsDeserializerDict()
    events = deserializer.deserialize([EVENT_1, EVENT_2])
    assert events[0].uid == "evt1@example.com"
    assert events[1].uid == "evt2@example.com"


def test_deserialize_empty():
    assert CalendarEventsDeserializerDict().deserialize([]) == []


def test_roundtrip():
    deserializer = CalendarEventsDeserializerDict()
    serializer = CalendarEventsSerializerDict()
    events_in = deserializer.deserialize([EVENT_1, EVENT_2])
    event_list_out = serializer.serialize(events_in)
    events_out = deserializer.deserialize(event_list_out)
    assert len(events_out) == len(events_in)
    assert events_out[0].uid == events_in[0].uid
    assert events_out[1].uid == events_in[1].uid
