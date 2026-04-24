"""
Unit tests for CalendarEventsSerializerDict.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventsSerializerDict import CalendarEventsSerializerDict


@pytest.fixture
def serializer():
    return CalendarEventsSerializerDict()


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
    assert serializer.serialize([]) == []


def test_serialize_structure(serializer, two_events):
    event_list = serializer.serialize(two_events)
    assert len(event_list) == 2
    assert event_list[0]["uid"] == "evt1@example.com"
