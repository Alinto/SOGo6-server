"""
Unit tests for CalendarEventsSerializerJson.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventsSerializerJson import CalendarEventsSerializerJson


@pytest.fixture
def serializer():
    return CalendarEventsSerializerJson()


@pytest.fixture
def two_events():
    return [
        CalEvent(
            uid="evt1@example.com", title="Standup",
            date_start=datetime(2026, 3, 19, 9, 30, tzinfo=timezone.utc),
            date_end=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
        ),
        CalEvent(
            uid="evt2@example.com", title="Review",
            date_start=datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc),
            date_end=datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc),
        ),
    ]


def test_empty_list(serializer):
    assert serializer.serialize([]) == "[]"


def test_to_response_structure(serializer, two_events):
    result = serializer.to_response(two_events)
    assert result["total_count"] == 2
    assert len(result["events"]) == 2
    assert result["events"][0]["uid"] == "evt1@example.com"
