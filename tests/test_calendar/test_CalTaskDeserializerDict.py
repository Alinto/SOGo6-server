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


def test_deserialize_anchors_start_on_due_date():
    """A task entered after it was due must not end up with a start later than its end."""
    task = _deserializer.deserialize({"title": "T", "date_due": "2020-01-15T12:00:00+00:00"})
    assert task.date_start == datetime(2020, 1, 15, 12, tzinfo=timezone.utc)
    assert task.date_start <= task.date_end


def test_deserialize_keeps_explicit_start_over_due():
    start = "2026-01-01T08:00:00+00:00"
    task = _deserializer.deserialize({"title": "T", "date_start": start, "date_due": "2026-02-01T00:00:00+00:00"})
    assert task.date_start == datetime(2026, 1, 1, 8, tzinfo=timezone.utc)


def test_deserialize_with_update_pulls_anchor_down_with_the_due_date():
    """Patching the due date below the anchored start must not invert the interval."""
    origin = CalEvent(
        uid="u", title="T", component_type=ComponentType.TASK,
        date_start=datetime(2026, 8, 10, tzinfo=timezone.utc), date_end=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )
    updated = _deserializer.deserialize_with_update(origin, {"date_due": "2026-07-01T00:00:00+00:00"})
    assert updated.date_start <= updated.date_end
    assert updated.date_start == datetime(2026, 7, 1, tzinfo=timezone.utc)


def test_deserialize_with_update_maps_due_and_keeps_origin_start():
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    origin = CalEvent(uid="u", title="Old", date_start=start, component_type=ComponentType.TASK)
    updated = _deserializer.deserialize_with_update(origin, {"date_due": "2026-07-01T00:00:00+00:00"})
    assert updated.date_end is not None
    assert updated.date_start == start  # untouched
