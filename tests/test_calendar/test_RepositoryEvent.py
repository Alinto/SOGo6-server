"""Unit tests for RepositoryEvent."""
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
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.utils.db.Condition import AndCondition, Condition, EqualCondition, FullTextCondition, OrCondition
from app.utils.db.FullTextValue import FullTextValue

_UTC = timezone.utc
_serializer = CalEventSerializerDict()


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

    def select_from_table(self, table_name, column_tuple, condition, limit=0, sort_by=None, offset=0, order=None, rank_by=None):
        self.last_select_condition = condition
        self.last_rank_by = rank_by
        return iter(self.select_result)

    def delete_row_in_table(self, table_name, condition, expected_row=0):
        self.deleted_rows = getattr(self, "deleted_rows", [])
        self.deleted_rows.append({"table": table_name, "cond": condition})
        return getattr(self, "delete_return", 0)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test event",
        date_start=datetime(2026, 3, 1, 9, 0, tzinfo=_UTC),
        date_end=datetime(2026, 3, 1, 10, 0, tzinfo=_UTC),
        calendar_key="cal-uuid-42",
        component_type=ComponentType.EVENT,
        status=EventStatus.CONFIRMED,
        visibility=EventVisibility.PUBLIC,
        show_as=ShowAs.BUSY,
        all_day=False,
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_row(event: CalEvent, event_id: int = 1) -> tuple:
    """Build a DB row tuple in ALL_EVT_COL order."""
    blob = _serializer.serialize(event)
    values = {
        "id": event_id,
        "key": event.key or "test-key",
        "calendar_key": event.calendar_key,
        "uid": event.uid,
        "component_type": event.component_type.value,
        "date_start": event.date_start,
        "date_end": event.date_end,
        "show_as": event.show_as.value,
        "is_recurring": event.recurrence_rule is not None,
        "date_end_recurrence": None,
        "recurrence_id": event.recurrence_id,
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
    assert result.db_id == 99
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


# ========== search_vector ==========

def test_search_vector_title_only():
    event = _make_event(title="Meeting")
    assert "meeting" in RepositoryEvent._build_search_vector(event)


def test_search_vector_includes_description_and_location():
    event = _make_event(title="Conf", description="Topic XYZ", location="Room A")
    assert "topic xyz" in RepositoryEvent._build_search_vector(event)
    assert "room a" in RepositoryEvent._build_search_vector(event)


def test_search_vector_strips_accents():
    event = _make_event(title="Réunion Joël", description="Café", location="Hôtel")
    sv = RepositoryEvent._build_search_vector(event)
    assert "reunion joel" in sv
    assert "cafe" in sv
    assert "hotel" in sv


def test_search_vector_folds_special_letters():
    event = _make_event(title="Søren cœur", description="Straße", location="Łódź")
    sv = RepositoryEvent._build_search_vector(event)
    assert "soren coeur" in sv
    assert "strasse" in sv
    assert "lodz" in sv


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


def test_insert_wraps_search_vector_for_fulltext():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1")
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    repo.insert(event)
    vals = db.inserted_rows[0]["vals"][0]
    col_idx = list(_INSERT_COLS).index("search_vector")
    assert isinstance(vals[col_idx], FullTextValue)


def test_insert_recurring_flag_set():
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
    col_idx = list(_INSERT_COLS).index("is_recurring")
    assert vals[col_idx] is True


def test_insert_non_recurring_flag_false():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1")
    db.select_result = [_build_row(event)]
    repo = RepositoryEvent(db)
    repo.insert(event)
    vals = db.inserted_rows[0]["vals"][0]
    col_idx = list(_INSERT_COLS).index("is_recurring")
    assert vals[col_idx] is False


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


def _contains_fulltext(condition: Condition) -> bool:
    if isinstance(condition, FullTextCondition):
        return True
    if isinstance(condition, (AndCondition, OrCondition)):
        return _contains_fulltext(condition.condition1) or _contains_fulltext(condition.condition2)
    return False


def test_find_by_calendar_search_uses_fulltext():
    db = FakeDB()
    db.select_result = []
    repo = RepositoryEvent(db)
    repo.find_by_calendar("cal-key-1", datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 1, 31, tzinfo=_UTC), search="budget")
    assert _contains_fulltext(db.last_select_condition)
    # Search results are ranked by relevance
    assert isinstance(db.last_rank_by, FullTextCondition)
    assert db.last_rank_by.query == "budget"


def test_find_by_calendar_no_search_has_no_fulltext():
    db = FakeDB()
    db.select_result = []
    repo = RepositoryEvent(db)
    repo.find_by_calendar("cal-key-1", datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 1, 31, tzinfo=_UTC))
    assert not _contains_fulltext(db.last_select_condition)
    assert db.last_rank_by is None


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


# ========== update ==========

def test_update_persists_changed_fields():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1", title="Updated title")
    event.db_id = 42
    event.key = "some-key"
    repo = RepositoryEvent(db)
    repo.update(event)
    assert len(db.updated_rows) == 1
    update = db.updated_rows[0]
    assert update["cond"].param_value == 42
    uid_idx = list(update["cols"]).index("uid")
    assert update["vals"][uid_idx] == "evt@example.com"


def test_update_requires_event_id():
    db = FakeDB()
    event = _make_event()
    event.db_id = None
    repo = RepositoryEvent(db)
    with pytest.raises(Exception):
        repo.update(event)


def test_update_sets_updated_at():
    db = FakeDB()
    event = _make_event(calendar_key="cal-key-1")
    event.db_id = 10
    repo = RepositoryEvent(db)
    repo.update(event)
    update = db.updated_rows[0]
    updated_at_idx = list(update["cols"]).index("updated_at")
    assert update["vals"][updated_at_idx] is not None


# ========== find_master_by_uid / find_detached_occurrences ==========

def _make_master(**kwargs):
    defaults = dict(
        uid="master@example.com",
        title="Weekly sync",
        date_start=datetime(2026, 3, 2, 9, 0, tzinfo=_UTC),
        date_end=datetime(2026, 3, 2, 10, 0, tzinfo=_UTC),
        calendar_key="cal-uuid-1",
        recurrence_rule=CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, interval=1, count=10),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def test_find_master_by_uid_returns_none_when_absent():
    db = FakeDB()
    db.select_result = []
    assert RepositoryEvent(db).find_master_by_uid("cal-key", "unknown@example.com") is None


def test_find_master_by_uid_returns_master():
    master = _make_master()
    master.key = "master-key"
    db = FakeDB()
    db.select_result = [_build_row(master)]
    result = RepositoryEvent(db).find_master_by_uid("cal-uuid-1", master.uid)
    assert result is not None
    assert result.uid == master.uid
    assert result.recurrence_rule is not None


def test_find_detached_occurrences_returns_rows():
    master = _make_master()
    rid = datetime(2026, 3, 9, 9, 0, tzinfo=_UTC)
    occ = CalEvent(
        uid=master.uid, title="Modified",
        date_start=rid, date_end=rid.replace(hour=11),
        calendar_key=master.calendar_key,
        recurrence_id=rid,
    )
    occ.key = "occ-key"
    db = FakeDB()
    db.select_result = [_build_row(occ, event_id=2)]
    result = RepositoryEvent(db).find_detached_occurrences("cal-uuid-1", master.uid)
    assert len(result) == 1
    assert result[0].recurrence_id == rid


# ========== delete_by_key ==========

def test_delete_by_key_sends_update():
    db = FakeDB()
    RepositoryEvent(db).delete_by_key("cal-key", "some-event-key")
    assert len(db.updated_rows) == 1
    update = db.updated_rows[0]
    is_deleted_idx = list(update["cols"]).index("is_deleted")
    assert update["vals"][is_deleted_idx] is True


# ========== purge_deleted ==========

def test_purge_deleted_calls_delete():
    db = FakeDB()
    db.delete_return = 5
    count = RepositoryEvent(db).purge_deleted("cal-key")
    assert count == 5
    assert len(db.deleted_rows) == 1
    assert db.deleted_rows[0]["table"] == "sogo6_calendar_events"
