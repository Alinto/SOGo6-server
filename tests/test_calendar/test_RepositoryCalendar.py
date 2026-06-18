"""Unit tests for RepositoryCalendar preferences mapping (JSON column <-> model fields)."""
from app.config.db import tables as tbl
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar

_COLS = tuple(col.name for col in tbl.ALL_CAL_COL)


def _row(**overrides):
    base = {name: None for name in _COLS}
    base.update(id=1, key="k", user_uid="u", is_default=False, source_type="local",
                name="Cal", timezone="UTC", ctag=0, include_in_freebusy=True)
    base.update(overrides)
    return tuple(base[name] for name in _COLS)


def _cal(**kwargs):
    return CalCalendar(key="k", user_uid="u", name="Cal", source_type=CalendarSourceType.LOCAL, **kwargs)


# ========== _row_to_calendar - unpack preferences ==========

def test_row_to_calendar_null_preferences_yields_none_defaults():
    cal = RepositoryCalendar._row_to_calendar(_row(preferences=None))
    assert cal.include_in_freebusy is True
    assert cal.default_event_duration_min is None
    assert cal.default_alarm_duration_min is None
    assert cal.default_type is None


def test_row_to_calendar_unpacks_preferences():
    prefs = {"default_event_duration_min": 45, "default_alarm_duration_min": 10, "default_type": "private"}
    cal = RepositoryCalendar._row_to_calendar(_row(preferences=prefs, include_in_freebusy=False))
    assert cal.include_in_freebusy is False
    assert cal.default_event_duration_min == 45
    assert cal.default_alarm_duration_min == 10
    assert cal.default_type == EventVisibility.PRIVATE


# ========== _pack_preferences ==========

def test_pack_preferences_all_unset_returns_none():
    assert RepositoryCalendar._pack_preferences(_cal()) is None


def test_pack_preferences_groups_set_fields_and_stores_enum_value():
    cal = _cal(default_event_duration_min=60, default_alarm_duration_min=5, default_type=EventVisibility.CONFIDENTIAL)
    assert RepositoryCalendar._pack_preferences(cal) == {
        "default_event_duration_min": 60,
        "default_alarm_duration_min": 5,
        "default_type": "confidential",
    }


def test_pack_then_unpack_round_trip():
    cal = _cal(default_event_duration_min=30, default_type=EventVisibility.PUBLIC)
    packed = RepositoryCalendar._pack_preferences(cal)
    restored = RepositoryCalendar._row_to_calendar(_row(preferences=packed))
    assert restored.default_event_duration_min == 30
    assert restored.default_alarm_duration_min is None
    assert restored.default_type == EventVisibility.PUBLIC
