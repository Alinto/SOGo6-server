"""Unit tests for calendar API Marshmallow schemas - applicative behaviour only.

Standard Marshmallow validation (required, length, type) is not retested here; only the
schema's own logic is covered: applicative defaults, the custom color regex, and the
date-only / naive-datetime normalisation to UTC.
"""
from datetime import timezone

import pytest
from marshmallow import ValidationError

from app.api.v1.calendar.schemas.calendar import CalendarCreateSchema
from app.api.v1.calendar.schemas.event import CalendarEventQueryArgsSchema
from app.api.v1.calendar.schemas.freebusy import FreeBusyRequestSchema

_UTC = timezone.utc


# ========== CalendarCreateSchema ==========

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


# ========== FreeBusyRequestSchema ==========

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
