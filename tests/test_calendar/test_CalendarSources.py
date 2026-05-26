"""Unit tests for CalendarSources public-subscription helpers."""
from unittest.mock import MagicMock

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.source.CalendarSources import CalendarSources


def _build_sources():
    sources = object.__new__(CalendarSources)
    sources._db = MagicMock()
    sources._repo_calendar = MagicMock()
    return sources


def _cal():
    return CalCalendar(key="cal-key", user_uid="u", name="Cal", source_type=CalendarSourceType.LOCAL)


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
