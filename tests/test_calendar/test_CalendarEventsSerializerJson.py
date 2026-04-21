"""
Unit tests for CalendarEventsSerializerJson.
Verifies that a list of CalEvent objects is correctly serialized to a JSON array.
"""
import json
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


def test_serialize_returns_valid_json(serializer, two_events):
    result = json.loads(serializer.serialize(two_events))
    assert isinstance(result, list)


def test_to_list_returns_list(serializer, two_events):
    assert isinstance(serializer.to_list(two_events), list)


def test_count(serializer, two_events):
    assert len(serializer.to_list(two_events)) == 2


def test_uids(serializer, two_events):
    items = serializer.to_list(two_events)
    assert items[0]["uid"] == "evt1@example.com"
    assert items[1]["uid"] == "evt2@example.com"


def test_empty_list(serializer):
    assert serializer.serialize([]) == "[]"


def test_event_fields_present(serializer, two_events):
    item = serializer.to_list(two_events)[0]
    assert "date_start" in item
    assert "date_end" in item
    assert "title" in item


def test_date_start_format(serializer, two_events):
    item = serializer.to_list(two_events)[0]
    assert item["date_start"] == "2026-03-19T09:30:00.000Z"
