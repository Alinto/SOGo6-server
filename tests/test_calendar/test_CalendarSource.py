"""
Unit tests for CalendarSource base class.

Covers: filter_date_start, filter_date_end, search (case + accent insensitive),
filter pipeline, get_events UTC normalization and default bounds.
"""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.source.CalendarSource import CalendarSource, _DEFAULT_START

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _event(uid, start, end, **kwargs):
    return CalEvent(uid=uid, title=kwargs.get("title", uid), date_start=start, date_end=end, **{
        k: v for k, v in kwargs.items() if k != "title"
    })


class FakeCalendarSource(CalendarSource):
    def __init__(self, events=None):
        super().__init__(CalCalendar(user_uid="test", name="Test"))
        self._events = events or []

    def _fetch_events(self, start, end):
        return list(self._events)


@pytest.fixture
def source():
    return FakeCalendarSource()


@pytest.fixture
def three_events():
    return [
        _event("e1", _dt(2026, 1, 1, 9), _dt(2026, 1, 1, 10), title="Morning standup"),
        _event("e2", _dt(2026, 1, 2, 14), _dt(2026, 1, 2, 15), title="Code review",
               description="Review pull request"),
        _event("e3", _dt(2026, 1, 3, 10), _dt(2026, 1, 3, 11), title="Planning",
               location="Conference room"),
    ]


# ========== filter_date_start ==========

def test_filter_date_start(source, three_events):
    # start = Jan 2 noon: e1 ended Jan 1 -> excluded
    result = source.filter_date_start(three_events, _dt(2026, 1, 2, 12))
    uids = [e.uid for e in result]
    assert "e1" not in uids
    assert "e2" in uids
    assert "e3" in uids


# ========== filter_date_end ==========

def test_filter_date_end(source, three_events):
    # end = Jan 1 noon: e2 and e3 start later -> excluded
    result = source.filter_date_end(three_events, _dt(2026, 1, 1, 12))
    uids = [e.uid for e in result]
    assert "e1" in uids
    assert "e2" not in uids
    assert "e3" not in uids


# ========== search ==========

def test_search_matches_title(source, three_events):
    assert len(source.search(three_events, "standup")) == 1


def test_search_case_insensitive(source, three_events):
    assert source.search(three_events, "STANDUP") == source.search(three_events, "standup")


def test_search_matches_description(source, three_events):
    result = source.search(three_events, "pull request")
    assert result[0].uid == "e2"


def test_search_matches_location(source, three_events):
    result = source.search(three_events, "conference")
    assert result[0].uid == "e3"


def test_search_no_match(source, three_events):
    assert source.search(three_events, "nonexistent") == []


def test_search_accent_insensitive(source):
    events = [_event("e1", _dt(2026, 1, 1), _dt(2026, 1, 1, 1), title="Réunion d'équipe")]
    assert len(source.search(events, "reunion")) == 1
    assert len(source.search(events, "equipe")) == 1


def test_search_accent_in_query(source):
    events = [_event("e1", _dt(2026, 1, 1), _dt(2026, 1, 1, 1), title="Etape finale")]
    assert len(source.search(events, "étape")) == 1


# ========== filter pipeline ==========

def test_filter_combines_date_range_and_search(source, three_events):
    result = source.filter(three_events, _dt(2026, 1, 1), _dt(2026, 1, 2, 23), "review")
    assert len(result) == 1
    assert result[0].uid == "e2"


# ========== get_events: UTC normalization and default bounds ==========

def test_default_start_includes_past_events():
    past = _event("past", _dt(2000, 1, 1, 9), _dt(2000, 1, 1, 10))
    source = FakeCalendarSource([past])
    events = source.get_events(start=None, end=_dt(2030, 1, 1))
    assert any(e.uid == "past" for e in events)


def test_default_end_excludes_far_future():
    future = _event("future", _dt(2099, 1, 1, 9), _dt(2099, 1, 1, 10))
    source = FakeCalendarSource([future])
    events = source.get_events(start=_DEFAULT_START, end=None)
    assert not any(e.uid == "future" for e in events)


def test_naive_datetime_treated_as_utc():
    past = _event("past", _dt(2000, 1, 1, 9), _dt(2000, 1, 1, 10))
    source = FakeCalendarSource([past])
    events = source.get_events(start=datetime(2000, 1, 1), end=datetime(2030, 1, 1))
    assert any(e.uid == "past" for e in events)
