"""Unit tests for CalendarSourceDb behaviour that is not a thin pass-through to the repository.

Focused on _upsert_reminder_if_relevant — the future-occurrence filter that keeps
sogo_calendar_reminders free of triggers that can never fire.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _build_source():
    source = object.__new__(CalendarSourceDb)
    source._calendar = CalCalendar(user_uid="u", name="C", key="cal-k", ctag=0)
    source._repo_reminder = MagicMock()
    return source


def _event(date_start, date_end, **kwargs):
    return CalEvent(uid="e@x", title="T", key="e-k", date_start=date_start, date_end=date_end, **kwargs)


# ========== _prepare_for_persistence — normalization + reminder resolution ==========

def test_prepare_for_persistence_normalizes_all_day():
    source = _build_source()
    start = _dt(2026, 4, 28)
    evt = _event(start, start, all_day=True)
    source._prepare_for_persistence(evt)
    assert evt.date_end == _dt(2026, 4, 29)


def test_prepare_for_persistence_resolves_reminder_from_calendar_default():
    source = _build_source()
    source._calendar.default_alarm_duration_min = 25
    evt = _event(_dt(2026, 4, 28, 9), _dt(2026, 4, 28, 10),
                 reminders=[CalReminder(method=ReminderMethod.POPUP)])
    source._prepare_for_persistence(evt)
    assert evt.reminders[0].minutes_before == 25


def test_upsert_relevant_when_non_recurring_future():
    source = _build_source()
    future = datetime.now(_UTC) + timedelta(days=7)
    source._upsert_reminder_if_relevant(_event(future, future + timedelta(hours=1)))
    source._repo_reminder.upsert.assert_called_once()
    source._repo_reminder.delete.assert_not_called()


def test_upsert_skipped_when_non_recurring_past():
    source = _build_source()
    past = datetime.now(_UTC) - timedelta(days=7)
    source._upsert_reminder_if_relevant(_event(past, past + timedelta(hours=1)))
    source._repo_reminder.upsert.assert_not_called()
    source._repo_reminder.delete.assert_called_once_with("e-k")


def test_upsert_relevant_when_recurring_unbounded():
    source = _build_source()
    past = datetime.now(_UTC) - timedelta(days=365)
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY)  # no UNTIL/COUNT → unbounded
    source._upsert_reminder_if_relevant(_event(past, past + timedelta(hours=1), recurrence_rule=rule))
    source._repo_reminder.upsert.assert_called_once()


def test_upsert_skipped_when_recurring_ended_in_the_past():
    source = _build_source()
    past = datetime.now(_UTC) - timedelta(days=365)
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, count=3)  # 3 weeks after past → still past
    source._upsert_reminder_if_relevant(_event(past, past + timedelta(hours=1), recurrence_rule=rule))
    source._repo_reminder.upsert.assert_not_called()
    source._repo_reminder.delete.assert_called_once_with("e-k")


def test_upsert_skipped_when_date_start_missing():
    source = _build_source()
    evt = CalEvent(uid="e@x", title="T", key="e-k")
    source._upsert_reminder_if_relevant(evt)
    source._repo_reminder.upsert.assert_not_called()
    source._repo_reminder.delete.assert_called_once_with("e-k")
