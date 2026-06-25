"""Unit tests for CalTaskSerializerDict (VTODO CalEvent -> task dict)."""
from datetime import datetime, timezone

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalTaskSerializerDict import CalTaskSerializerDict

_serializer = CalTaskSerializerDict()


def _task(**kwargs):
    defaults = {"uid": "u", "title": "T", "date_start": datetime(2026, 3, 1, tzinfo=timezone.utc),
                "component_type": ComponentType.TASK}
    defaults.update(kwargs)
    return CalEvent(**defaults)


def test_serialize_exposes_date_end_as_due():
    result = _serializer.serialize(_task(date_end=datetime(2026, 6, 15, tzinfo=timezone.utc)))
    assert "2026-06-15" in result["date_due"]
    assert "date_end" not in result


def test_serialize_without_due_returns_null():
    assert _serializer.serialize(_task(date_end=None))["date_due"] is None
