"""Unit tests for RepositoryEvent."""
import json
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent, _ALL_COLS, _INSERT_COLS
from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson
from app.utils.db.Condition import (AndCondition, EqualCondition, GreaterOrEqualCondition,
                                     IsNotNullCondition, IsNullCondition, LessOrEqualCondition,
                                     OrCondition)

_UTC = timezone.utc
_serializer = CalendarEventSerializerJson()


class FakeDB:
    """Minimal fake ClientSQL for RepositoryEvent tests."""

    def __init__(self):
        self.inserted_rows = []
        self.updated_rows = []
        self.select_result = []
        self.insert_return = 1

    def insert_in_table(self, table_name, column_tuple, values_tuple):
        self.inserted_rows.append({"table": table_name, "cols": column_tuple, "vals": values_tuple})
        return self.insert_return

    def update_in_table(self, table_name, column_tuple, values_list, condition):
        self.updated_rows.append({"table": table_name, "cols": column_tuple, "vals": values_list, "cond": condition})
        return 1

    def select_from_table(self, table_name, column_tuple, condition, limit=0, sort_by=None, offset=0, order=None):
        return iter(self.select_result)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test event",
        date_start=datetime(2026, 3, 1, 9, 0, tzinfo=_UTC),
        date_end=datetime(2026, 3, 1, 10, 0, tzinfo=_UTC),
        calendar_key="cal-uuid-42",
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_row(event: CalEvent, event_id: int = 1) -> tuple:
    """Build a DB row tuple in ALL_EVT_COL order."""
    blob = _serializer.to_dict(event)
    rrule_dict = event.recurrence_rule.to_dict() if event.recurrence_rule else None
    values = {
        "id": event_id,
        "key": event.key or "test-key",
        "calendar_key": event.calendar_key,
        "uid": event.uid,
        "component_type": event.component_type.value,
        "date_start": event.date_start,
        "date_end": event.date_end,
        "show_as": event.show_as.value,
        "rrule": rrule_dict,
        "date_end_recurrence": None,
        "recurrence_id": event.recurrence_id,
        "parent_id": None,
        "is_deleted": False,
        "sequence": event.sequence,
        "search_vector": event.title,
        "cal_event": blob,
        "created_at": event.created_at or datetime(2026, 1, 1, tzinfo=_UTC),
        "updated_at": event.updated_at or datetime(2026, 1, 1, tzinfo=_UTC),
    }
    return tuple(values[col] for col in _ALL_COLS)


@pytest.fixture
def repo():
    return RepositoryEvent(FakeDB())


# ========== _row_to_event ==========

def test_row_to_event_sets_relational_fields():
    event = _make_event(calendar_key="cal-uuid-7")
    event.key = "abc"
    row = _build_row(event, event_id=99)
    result = RepositoryEvent._row_to_event(row)  # pylint: disable=protected-access
    assert result.id == "99"
    assert result.key == "abc"
    assert result.calendar_key == "cal-uuid-7"
    assert result.uid == "evt@example.com"
    assert result.component_type == ComponentType.EVENT


def test_row_to_event_datetimes_are_utc_aware():
    event = _make_event()
    event.key = "k"
    row = _build_row(event)
    result = RepositoryEvent._row_to_event(row)  # pylint: disable=protected-access
    assert result.date_start.tzinfo is not None
    assert result.date_end.tzinfo is not None


def test_row_to_event_naive_timestamps_made_utc():
    event = _make_event()
    event.key = "k"
    row = list(_build_row(event))
    # Simulate psycopg returning naive datetime
    col_idx = list(_ALL_COLS).index("date_start")
    row[col_idx] = datetime(2026, 3, 1, 9, 0)  # naive
    result = RepositoryEvent._row_to_event(tuple(row))  # pylint: disable=protected-access
    assert result.date_start.tzinfo == _UTC


def test_row_to_event_preserves_blob_title():
    event = _make_event(title="My special event")
    event.key = "k"
    row = _build_row(event)
    result = RepositoryEvent._row_to_event(row)  # pylint: disable=protected-access
    assert result.title == "My special event"


# ========== _build_search_vector ==========

def test_search_vector_title_only():
    event = _make_event(title="Meeting")
    vec = RepositoryEvent._build_search_vector(event)  # pylint: disable=protected-access
    assert "Meeting" in vec


def test_search_vector_includes_description_and_location():
    event = _make_event(title="Conf", description="Topic XYZ", location="Room A")
    vec = RepositoryEvent._build_search_vector(event)  # pylint: disable=protected-access
    assert "Topic XYZ" in vec
    assert "Room A" in vec


# ========== insert ==========

def test_insert_generates_key():
    db = FakeDB()
    db.select_result = [_build_row(_make_event())]
    event = _make_event(calendar_key="cal-key-1")
    repo = RepositoryEvent(db)
    result = repo.insert(event)
    assert result is not None
    assert len(db.inserted_rows) == 1


def test_insert_cols_count_matches():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1")
    event.key = "pre-set"
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    repo.insert(event)
    row = db.inserted_rows[0]
    assert len(row["cols"]) == len(row["vals"][0])


def test_insert_sets_is_deleted_false():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1")
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    repo.insert(event)
    vals = db.inserted_rows[0]["vals"][0]
    col_idx = list(_INSERT_COLS).index("is_deleted")
    assert vals[col_idx] is False


def test_insert_rrule_stored():
    db = FakeDB()
    event = _make_event(
        calendar_key="cal-key-1",
        recurrence_rule=CalRecurrenceRule(
            frequency=RecurrenceFrequency.DAILY,
            count=5,
        ),
    )
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    repo.insert(event)
    vals = db.inserted_rows[0]["vals"][0]
    col_idx = list(_INSERT_COLS).index("rrule")
    rrule_dict = vals[col_idx]
    assert rrule_dict["frequency"] == "daily"
    assert rrule_dict["count"] == 5


# ========== delete and delete_all ==========

def test_delete_sets_is_deleted_true():
    db = FakeDB()
    repo = RepositoryEvent(db)
    repo.delete(calendar_key="cal-key-1", uid="evt@example.com")
    assert len(db.updated_rows) == 1
    update = db.updated_rows[0]
    is_deleted_idx = list(update["cols"]).index("is_deleted")
    assert update["vals"][is_deleted_idx] is True


def test_delete_all_targets_calendar_key():
    db = FakeDB()
    repo = RepositoryEvent(db)
    repo.delete_all(calendar_key="cal-key-42")
    assert len(db.updated_rows) == 1
    cond = db.updated_rows[0]["cond"]
    assert isinstance(cond, EqualCondition)
    assert cond.param_value == "cal-key-42"


# ========== find_by_calendar condition structure ==========

def test_find_by_calendar_returns_empty_on_no_rows():
    db = FakeDB()
    db.select_result = []
    repo = RepositoryEvent(db)
    result = repo.find_by_calendar("cal-key-1", datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 1, 31, tzinfo=_UTC))
    assert result == []


def test_find_by_calendar_maps_rows():
    event = _make_event(calendar_key="cal-key-1")
    event.key = "k"
    db = FakeDB()
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    results = repo.find_by_calendar("cal-key-1", datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 12, 31, tzinfo=_UTC))
    assert len(results) == 1
    assert results[0].uid == "evt@example.com"


# ========== find_by_key ==========

def test_find_by_key_returns_none_when_empty():
    db = FakeDB()
    db.select_result = []
    repo = RepositoryEvent(db)
    assert repo.find_by_key("cal-key-5", "missing-key") is None


def test_find_by_key_returns_event():
    event = _make_event(calendar_key="cal-key-5")
    event.key = "my-key"
    db = FakeDB()
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    result = repo.find_by_key("cal-key-5", "my-key")
    assert result is not None
    assert result.uid == "evt@example.com"
