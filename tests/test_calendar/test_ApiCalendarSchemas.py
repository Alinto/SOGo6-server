"""Unit tests for calendar API Marshmallow schemas."""
from datetime import timezone

import pytest
from marshmallow import ValidationError

from app.api.v1.calendar.schemas.calendar import CalendarCreateSchema, CalendarUpdateSchema
from app.api.v1.calendar.schemas.event import CalendarEventQueryArgsSchema
from app.api.v1.calendar.schemas.freebusy import FreeBusyRequestSchema

_UTC = timezone.utc


# ========== CalendarCreateSchema ==========

def test_create_requires_name():
    schema = CalendarCreateSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({})
    assert "name" in exc.value.messages


def test_create_defaults():
    schema = CalendarCreateSchema()
    result = schema.load({"name": "Work"})
    assert result["name"] == "Work"
    assert result["color"] == "#3B82F6"
    assert result["timezone"] == "UTC"
    assert result["description"] is None


def test_create_invalid_color():
    schema = CalendarCreateSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"name": "Work", "color": "red"})
    assert "color" in exc.value.messages


def test_create_valid_color():
    schema = CalendarCreateSchema()
    result = schema.load({"name": "Work", "color": "#FF0000"})
    assert result["color"] == "#FF0000"


def test_create_name_too_short():
    schema = CalendarCreateSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"name": ""})
    assert "name" in exc.value.messages


# ========== CalendarUpdateSchema ==========

def test_update_all_optional():
    schema = CalendarUpdateSchema()
    result = schema.load({})
    assert result == {}


def test_update_invalid_color():
    schema = CalendarUpdateSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"color": "not-a-color"})
    assert "color" in exc.value.messages


def test_update_valid_partial():
    schema = CalendarUpdateSchema()
    result = schema.load({"name": "Personal", "is_default": True})
    assert result["name"] == "Personal"
    assert result["is_default"] is True


# ========== FreeBusyRequestSchema ==========

def test_freebusy_requires_target_uids():
    schema = FreeBusyRequestSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"start": "2026-04-22T00:00:00Z", "end": "2026-04-22T23:59:59Z"})
    assert "target_uids" in exc.value.messages


def test_freebusy_requires_start():
    schema = FreeBusyRequestSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"target_uids": ["u@example.com"], "end": "2026-04-22T23:59:59Z"})
    assert "start" in exc.value.messages


def test_freebusy_requires_end():
    schema = FreeBusyRequestSchema()
    with pytest.raises(ValidationError) as exc:
        schema.load({"target_uids": ["u@example.com"], "start": "2026-04-22T00:00:00Z"})
    assert "end" in exc.value.messages


def test_freebusy_end_date_only_defaults_to_end_of_day():
    schema = FreeBusyRequestSchema()
    result = schema.load({
        "target_uids": ["u@example.com"],
        "start": "2026-04-22T00:00:00Z",
        "end": "2026-04-22",
    })
    assert result["end"].hour == 23
    assert result["end"].second == 59


def test_freebusy_valid():
    schema = FreeBusyRequestSchema()
    result = schema.load({
        "target_uids": ["a@example.com", "b@example.com"],
        "start": "2026-04-22T00:00:00Z",
        "end": "2026-04-22T23:59:59Z",
    })
    assert len(result["target_uids"]) == 2
    assert result["start"].tzinfo is not None
    assert result["end"].tzinfo is not None


# ========== CalendarEventQueryArgsSchema ==========

def test_query_end_date_only_defaults_to_end_of_day():
    dt = CalendarEventQueryArgsSchema().load({"end_date_time": "2026-04-09"})["end_date_time"]
    assert (dt.hour, dt.minute, dt.second) == (23, 59, 59)
    assert dt.tzinfo == _UTC


def test_query_start_date_only_keeps_midnight():
    dt = CalendarEventQueryArgsSchema().load({"start_date_time": "2026-01-01"})["start_date_time"]
    assert (dt.hour, dt.minute, dt.second) == (0, 0, 0)
    assert dt.tzinfo == _UTC


def test_query_naive_datetime_normalized_to_utc():
    dt = CalendarEventQueryArgsSchema().load({"start_date_time": "2026-01-01T09:00:00"})["start_date_time"]
    assert dt.tzinfo == _UTC
    assert dt.hour == 9


def test_query_absent_fields_are_none():
    result = CalendarEventQueryArgsSchema().load({})
    assert result["start_date_time"] is None
    assert result["end_date_time"] is None
