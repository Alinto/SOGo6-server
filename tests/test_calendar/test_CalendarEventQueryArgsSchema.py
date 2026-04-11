"""
Unit tests for CalendarEventQueryArgsSchema.
Validates UTC enforcement and end-of-day defaulting for date-only inputs.
"""
from datetime import timezone

import pytest

from app.api.v1.calendar.schemas.event import CalendarEventQueryArgsSchema

_UTC = timezone.utc


@pytest.fixture
def schema() -> CalendarEventQueryArgsSchema:
    return CalendarEventQueryArgsSchema()


def test_end_date_only_defaults_to_end_of_day(schema):
    dt = schema.load({"end_date_time": "2026-04-09"})["end_date_time"]
    assert (dt.hour, dt.minute, dt.second) == (23, 59, 59)
    assert dt.tzinfo == _UTC


def test_start_date_only_keeps_midnight(schema):
    """start_date_time with date-only stays at 00:00:00 — no end-of-day defaulting."""
    dt = schema.load({"start_date_time": "2026-01-01"})["start_date_time"]
    assert (dt.hour, dt.minute, dt.second) == (0, 0, 0)
    assert dt.tzinfo == _UTC


def test_naive_datetime_normalized_to_utc(schema):
    dt = schema.load({"start_date_time": "2026-01-01T09:00:00"})["start_date_time"]
    assert dt.tzinfo == _UTC
    assert dt.hour == 9


def test_absent_fields_are_none(schema):
    result = schema.load({})
    assert result["start_date_time"] is None
    assert result["end_date_time"] is None
