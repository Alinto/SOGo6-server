"""Unit tests for RepositoryReminder."""
from datetime import datetime, timedelta, timezone

import pytest

from app.config.db import tables as tbl
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.repository.RepositoryReminder import RepositoryReminder

_UTC = timezone.utc


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


class FakeDB:
    """Minimal fake ClientSQL for RepositoryReminder tests."""

    def __init__(self):
        self.inserted_rows = []
        self.updated_rows = []
        self.deleted_conditions = []
        self.join_result = []

    def insert_in_table(self, table_name, column_tuple, values_tuple):
        self.inserted_rows.append({"table": table_name, "cols": column_tuple, "vals": values_tuple})
        return 1

    def update_in_table(self, table_name, column_tuple, values_list, condition):
        self.updated_rows.append({"table": table_name, "cols": column_tuple, "vals": values_list, "cond": condition})
        return 1

    def delete_row_in_table(self, table_name, condition, expected_row=0):
        self.deleted_conditions.append({"table": table_name, "cond": condition})
        return 1

    def select_from_several_table(self, table_name, joins, column_tuple, condition, sort_by=None, order=None, limit=0):
        return iter(self.join_result)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        date_start=_dt(2026, 6, 1, 10, 0),
        date_end=_dt(2026, 6, 1, 11, 0),
        key="evt-key-1",
        calendar_key="cal-key-1",
        reminders=[
            CalReminder(method=ReminderMethod.POPUP, minutes_before=15),
        ],
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _build_join_row(event_key, method, minutes_before, trigger_at, date_start, date_end, is_recurring,
                    user_uid="user@example.com"):
    """Build a row tuple matching the _FIND_COLS order from find_pending JOIN."""
    return (event_key, method, minutes_before, trigger_at, date_start, date_end, is_recurring, user_uid)


# ========== upsert_for_event ==========

def test_upsert_inserts_reminder_rows():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event()
    repo.upsert(event)
    assert len(db.inserted_rows) == 1
    vals = db.inserted_rows[0]["vals"][0]
    assert vals[0] == "evt-key-1"
    assert vals[1] == "popup"
    assert vals[2] == 15


def test_upsert_computes_trigger_at():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event()
    repo.upsert(event)
    trigger_at = db.inserted_rows[0]["vals"][0][3]
    expected = _dt(2026, 6, 1, 9, 45)
    assert trigger_at == expected


def test_upsert_sets_is_deleted_false():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event()
    repo.upsert(event)
    is_deleted = db.inserted_rows[0]["vals"][0][4]
    assert is_deleted is False


def test_upsert_soft_deletes_before_insert():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event()
    repo.upsert(event)
    assert len(db.updated_rows) == 1
    assert db.updated_rows[0]["vals"][0] is True
    assert db.updated_rows[0]["vals"][1] is not None


def test_upsert_multiple_reminders():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event(reminders=[
        CalReminder(method=ReminderMethod.POPUP, minutes_before=15),
        CalReminder(method=ReminderMethod.EMAIL, minutes_before=60),
    ])
    repo.upsert(event)
    assert len(db.inserted_rows) == 2


def test_upsert_no_reminders_only_deletes():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event(reminders=[])
    repo.upsert(event)
    assert len(db.updated_rows) == 1
    assert len(db.inserted_rows) == 0


def test_upsert_no_date_start_only_deletes():
    db = FakeDB()
    repo = RepositoryReminder(db)
    event = _make_event(date_start=None)
    repo.upsert(event)
    assert len(db.updated_rows) == 1
    assert len(db.inserted_rows) == 0


# ========== delete_for_event ==========

def test_delete_soft_deletes():
    db = FakeDB()
    repo = RepositoryReminder(db)
    repo.delete("evt-key-1")
    assert len(db.updated_rows) == 1
    assert db.updated_rows[0]["vals"][0] is True
    assert db.updated_rows[0]["vals"][1] is not None


# ========== purge_deleted ==========

def test_purge_deleted_all():
    db = FakeDB()
    repo = RepositoryReminder(db)
    repo.purge_deleted()
    assert len(db.deleted_conditions) == 1


def test_purge_deleted_by_event_key():
    db = FakeDB()
    repo = RepositoryReminder(db)
    repo.purge_deleted(event_key="evt-key-1")
    assert len(db.deleted_conditions) == 1


# ========== find_pending ==========

def test_find_pending_returns_models():
    db = FakeDB()
    trigger = _dt(2026, 6, 1, 9, 45)
    db.join_result = [
        _build_join_row("evt-key-1", "popup", 15, trigger,
                        _dt(2026, 6, 1, 10), _dt(2026, 6, 1, 11), False),
    ]
    repo = RepositoryReminder(db)
    results = repo.find_pending(_dt(2026, 6, 1, 9, 40), _dt(2026, 6, 1, 9, 50))
    assert len(results) == 1
    assert isinstance(results[0], CalEventReminder)
    assert results[0].event_key == "evt-key-1"
    assert results[0].method == ReminderMethod.POPUP
    assert results[0].minutes_before == 15
    assert results[0].trigger_at == trigger
    assert results[0].date_start == _dt(2026, 6, 1, 10)
    assert results[0].date_end == _dt(2026, 6, 1, 11)
    assert results[0].title is None
    assert results[0].location is None


def test_find_pending_empty():
    db = FakeDB()
    db.join_result = []
    repo = RepositoryReminder(db)
    results = repo.find_pending(_dt(2026, 6, 1), _dt(2026, 6, 2))
    assert results == []
