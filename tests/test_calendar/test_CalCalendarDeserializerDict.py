"""Unit tests for CalCalendarDeserializerDict (create + partial update parsing)."""
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.serializer.CalCalendarDeserializerDict import CalCalendarDeserializerDict

_deserializer = CalCalendarDeserializerDict()


def test_deserialize_maps_fields_and_default_type():
    cal = _deserializer.deserialize({
        "name": "Work", "color": "#FF0000", "default_type": "private",
        "include_in_freebusy": False, "default_event_duration_min": 45,
    })
    assert cal.name == "Work"
    assert cal.color == "#FF0000"
    assert cal.default_type == EventVisibility.PRIVATE
    assert cal.include_in_freebusy is False
    assert cal.default_event_duration_min == 45


def test_deserialize_default_type_absent_stays_none():
    assert _deserializer.deserialize({"name": "Work"}).default_type is None


def test_deserialize_with_update_merges_mutable_and_coerces_default_type():
    origin = CalCalendar(key="k", user_uid="u", name="Old", color="#000000")
    merged = _deserializer.deserialize_with_update(origin, {"name": "New", "default_type": "confidential"})
    assert merged.name == "New"
    assert merged.default_type == EventVisibility.CONFIDENTIAL
    assert merged.color == "#000000"  # untouched fields preserved
    assert origin.name == "Old"  # origin not mutated


def test_deserialize_with_update_ignores_immutable_fields():
    origin = CalCalendar(key="k", user_uid="u", name="C")
    merged = _deserializer.deserialize_with_update(origin, {"key": "other", "user_uid": "intruder"})
    assert merged.key == "k"
    assert merged.user_uid == "u"
