"""Unit tests for CalTaskDeserializerDict (task dict -> VTODO CalEvent)."""
from datetime import datetime, timezone

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalTaskDeserializerDict import CalTaskDeserializerDict

_deserializer = CalTaskDeserializerDict()


def test_deserialize_maps_due_and_marks_task():
    task = _deserializer.deserialize({"title": "T", "date_due": "2026-05-01T00:00:00+00:00"})
    assert task.component_type == ComponentType.TASK
    assert task.date_end is not None  # date_due lands on the model's date_end


def test_deserialize_defaults_start_when_absent():
    # A VTODO with no explicit start gets an anchor so the component is always datable.
    assert _deserializer.deserialize({"title": "T"}).date_start is not None


def test_deserialize_with_update_maps_due_and_keeps_origin_start():
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    origin = CalEvent(uid="u", title="Old", date_start=start, component_type=ComponentType.TASK)
    updated = _deserializer.deserialize_with_update(origin, {"date_due": "2026-07-01T00:00:00+00:00"})
    assert updated.date_end is not None
    assert updated.date_start == start  # untouched
