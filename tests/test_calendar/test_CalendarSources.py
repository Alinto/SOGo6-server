"""Unit tests for CalendarSources public-subscription helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction, ScopeResult
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


# ========== propagate - replicate touched to attendees ==========

def _organized_event(attendees=("alice@x",), organizer="boss@x", **kwargs):
    return _event(9, organizer=CalOrganizer(email=organizer),
                  attendees=[CalAttendee(email=a) for a in attendees], **kwargs)


def test_propagate_update_applies_organizer_content_to_attendee_copy():
    sources = object.__new__(CalendarSources)
    att_copy = _event(9)
    att_copy.title = "Old"
    att_source = MagicMock()
    att_source.get_master_event_by_uid.return_value = att_copy
    sources._resolve_attendee_source = MagicMock(return_value=att_source)
    updated = _organized_event()
    updated.title = "New"
    sources.propagate(ScopeResult(result=updated, touched=[(updated, EventAction.UPDATE)]))
    att_source.update_event.assert_called_once_with(att_copy)
    assert att_copy.title == "New"  # propagatable field carried onto the attendee's copy


def test_propagate_delete_master_removes_attendee_copy():
    sources = object.__new__(CalendarSources)
    att_source = MagicMock()
    sources._resolve_attendee_source = MagicMock(return_value=att_source)
    ev = _organized_event()
    sources.propagate(ScopeResult(result=ev, touched=[(ev, EventAction.DELETE)]))
    att_source.delete_event.assert_called_once_with("e9")
    att_source.delete_occurrence.assert_not_called()


def test_propagate_delete_occurrence_removes_attendee_occurrence():
    sources = object.__new__(CalendarSources)
    att_occ = _event(9)
    att_source = MagicMock()
    att_source.get_event_by_recurrence_id.return_value = att_occ
    sources._resolve_attendee_source = MagicMock(return_value=att_source)
    rid = datetime(2026, 6, 3, 9, tzinfo=timezone.utc)
    ev = _organized_event(recurrence_id=rid)
    sources.propagate(ScopeResult(result=ev, touched=[(ev, EventAction.DELETE)]))
    att_source.get_event_by_recurrence_id.assert_called_once_with("e9", rid)
    att_source.delete_occurrence.assert_called_once_with(att_occ)
    att_source.delete_event.assert_not_called()


def test_propagate_skips_organizer_and_external_attendees():
    sources = object.__new__(CalendarSources)
    local = MagicMock()
    sources._resolve_attendee_source = MagicMock(side_effect=lambda email: local if email == "alice@x" else None)
    ev = _organized_event(attendees=("boss@x", "alice@x", "bob@x"), organizer="boss@x")
    sources.propagate(ScopeResult(result=ev, touched=[(ev, EventAction.DELETE)]))
    local.delete_event.assert_called_once_with("e9")
    # organizer skipped before resolution; only alice and bob are resolved (bob is external -> skipped)
    assert sources._resolve_attendee_source.call_count == 2


def test_propagate_no_attendees_is_noop():
    sources = object.__new__(CalendarSources)
    sources._resolve_attendee_source = MagicMock()
    ev = _event(9, organizer=CalOrganizer(email="boss@x"), attendees=[])
    sources.propagate(ScopeResult(result=ev, touched=[(ev, EventAction.DELETE)]))
    sources._resolve_attendee_source.assert_not_called()


# ========== _sync_attendee_list - add / remove attendee copies ==========

def test_sync_attendee_list_adds_copy_for_new_attendee():
    sources = object.__new__(CalendarSources)
    new_src = MagicMock()
    new_src.calendar.key = "bob-cal"
    sources._resolve_attendee_source = MagicMock(return_value=new_src)
    original = _organized_event(attendees=("boss@x", "alice@x"), organizer="boss@x")
    updated = _organized_event(attendees=("boss@x", "alice@x", "bob@x"), organizer="boss@x")
    sources._sync_attendee_list(original=original, updated=updated)
    sources._resolve_attendee_source.assert_called_once_with("bob@x")  # only the added one
    new_src.insert_event.assert_called_once()


def test_sync_attendee_list_removes_copy_for_dropped_attendee():
    sources = object.__new__(CalendarSources)
    drop_src = MagicMock()
    sources._resolve_attendee_source = MagicMock(return_value=drop_src)
    original = _organized_event(attendees=("boss@x", "alice@x", "bob@x"), organizer="boss@x")
    updated = _organized_event(attendees=("boss@x", "alice@x"), organizer="boss@x")
    sources._sync_attendee_list(original=original, updated=updated)
    sources._resolve_attendee_source.assert_called_once_with("bob@x")
    drop_src.delete_event.assert_called_once_with("e9")


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
