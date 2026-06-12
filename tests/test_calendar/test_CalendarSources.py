"""Unit tests for CalendarSources public-subscription helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.source.CalendarSources import CalendarSources


def _build_sources():
    sources = object.__new__(CalendarSources)
    sources._db = MagicMock()
    sources._repo_calendar = MagicMock()
    return sources


def _cal(include_in_freebusy=True):
    cal = CalCalendar(key="cal-key", user_uid="u", name="Cal", source_type=CalendarSourceType.LOCAL)
    cal.include_in_freebusy = include_in_freebusy
    return cal


def _event(hour):
    return CalEvent(uid=f"e{hour}", title="E", date_start=datetime(2026, 6, 1, hour, tzinfo=timezone.utc),
                    date_end=datetime(2026, 6, 1, hour + 1, tzinfo=timezone.utc))


def test_get_by_share_token_returns_source_when_found():
    sources = _build_sources()
    sources._repo_calendar.find_by_share_token.return_value = _cal()
    source = sources.get_by_share_token("tok")
    assert source is not None
    assert source.calendar.key == "cal-key"


def test_get_by_share_token_returns_none_when_absent():
    sources = _build_sources()
    sources._repo_calendar.find_by_share_token.return_value = None
    assert sources.get_by_share_token("tok") is None


# ========== get_freebusy_events ==========

def test_get_freebusy_events_excludes_non_participating_calendars():
    sources = _build_sources()
    src_in = MagicMock(calendar=_cal(include_in_freebusy=True))
    src_in.get_events.return_value = [_event(9)]
    src_out = MagicMock(calendar=_cal(include_in_freebusy=False))
    src_out.get_events.return_value = [_event(11)]
    sources.get_all = MagicMock(return_value=[src_in, src_out])

    events = sources.get_freebusy_events("u")

    assert [e.uid for e in events] == ["e9"]
    src_out.get_events.assert_not_called()


def test_get_freebusy_events_merges_and_sorts_participating_calendars():
    sources = _build_sources()
    src_a = MagicMock(calendar=_cal())
    src_a.get_events.return_value = [_event(14)]
    src_b = MagicMock(calendar=_cal())
    src_b.get_events.return_value = [_event(8)]
    sources.get_all = MagicMock(return_value=[src_a, src_b])

    events = sources.get_freebusy_events("u")

    assert [e.uid for e in events] == ["e8", "e14"]
