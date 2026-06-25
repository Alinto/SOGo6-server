"""Unit tests for CalendarSources public-subscription helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction
from app.module.calendar.source.CalendarSources import CalendarSources
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _build_sources():
    sources = object.__new__(CalendarSources)
    sources._db = MagicMock()
    sources._repo_calendar = MagicMock()
    return sources


def _cal(include_in_freebusy=True):
    cal = CalCalendar(key="cal-key", user_uid="u", name="Cal", source_type=CalendarSourceType.LOCAL)
    cal.include_in_freebusy = include_in_freebusy
    return cal


def _event(hour, **kwargs):
    return CalEvent(uid=f"e{hour}", title="E", date_start=datetime(2026, 6, 1, hour, tzinfo=timezone.utc),
                    date_end=datetime(2026, 6, 1, hour + 1, tzinfo=timezone.utc), **kwargs)


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


# ========== _apply_action - INSERT reminder handling ==========

def test_apply_action_insert_carries_attendee_reminders_on_split():
    """A split sub-series propagated to an attendee carries that attendee's own reminders."""
    sources = object.__new__(CalendarSources)
    reminder = CalReminder(method=ReminderMethod.POPUP, minutes_before=15)
    origin = _event(9, reminders=[reminder])
    att_source = MagicMock()
    att_source.calendar.key = "att-cal"
    att_source.get_master_event_by_uid.return_value = origin
    new_sub = _event(14, uid_parent_split="orig-uid", reminders=[])
    sources._apply_action(att_source, new_sub, EventAction.INSERT)
    inserted = att_source.insert_event.call_args[0][0]
    assert inserted.reminders == [reminder]


def test_apply_action_insert_strips_reminders_for_plain_event():
    """A non-split insert never inherits the organizer's reminders."""
    sources = object.__new__(CalendarSources)
    att_source = MagicMock()
    att_source.calendar.key = "att-cal"
    new_evt = _event(9, reminders=[CalReminder(method=ReminderMethod.POPUP, minutes_before=15)])
    sources._apply_action(att_source, new_evt, EventAction.INSERT)
    inserted = att_source.insert_event.call_args[0][0]
    assert inserted.reminders == []


# ========== require_event ==========

def test_require_event_returns_source_and_event():
    sources = _build_sources()
    event = _event(9)
    src = MagicMock(calendar=_cal())
    src.get_event.side_effect = lambda key: event if key == "k" else None
    sources.get_all = MagicMock(return_value=[src])
    found_source, found_event = sources.require_event("u", "k")
    assert found_source is src
    assert found_event is event


def test_require_event_raises_when_absent():
    sources = _build_sources()
    src = MagicMock(calendar=_cal())
    src.get_event.return_value = None
    sources.get_all = MagicMock(return_value=[src])
    with pytest.raises(RequestException) as exc:
        sources.require_event("u", "missing")
    assert exc.value.error == err.ERROR_CALENDAR_EVENT_NOT_FOUND


# ========== get_freebusy_events ==========

def test_get_freebusy_events_excludes_non_participating_calendars():
    sources = _build_sources()
    src_in = MagicMock(calendar=_cal(include_in_freebusy=True))
    src_in.get_all_events.return_value = [_event(9)]
    src_out = MagicMock(calendar=_cal(include_in_freebusy=False))
    src_out.get_all_events.return_value = [_event(11)]
    sources.get_all = MagicMock(return_value=[src_in, src_out])

    events = sources.get_freebusy_events("u")

    assert [e.uid for e in events] == ["e9"]
    src_out.get_all_events.assert_not_called()


def test_get_freebusy_events_merges_and_sorts_participating_calendars():
    sources = _build_sources()
    src_a = MagicMock(calendar=_cal())
    src_a.get_all_events.return_value = [_event(14)]
    src_b = MagicMock(calendar=_cal())
    src_b.get_all_events.return_value = [_event(8)]
    sources.get_all = MagicMock(return_value=[src_a, src_b])

    events = sources.get_freebusy_events("u")

    assert [e.uid for e in events] == ["e8", "e14"]
