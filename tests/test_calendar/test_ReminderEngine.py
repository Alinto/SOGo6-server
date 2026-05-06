"""Unit tests for ReminderEngine."""
from datetime import datetime, timedelta, timezone

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.reminder.ReminderEngine import ReminderEngine

_UTC = timezone.utc


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        location="Room A",
        date_start=_dt(2026, 6, 1, 10, 0),
        date_end=_dt(2026, 6, 1, 11, 0),
        key="evt-key",
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


_UNSET = object()


def _row(event_key="evt-key", method="popup", minutes_before=15, trigger_at=None, is_recurring=False,
         title="Test", location="Room A", date_start=_UNSET, date_end=_UNSET):
    return {
        "event_key": event_key,
        "method": method,
        "minutes_before": minutes_before,
        "trigger_at": trigger_at or _dt(2026, 6, 1, 9, 45),
        "is_recurring": is_recurring,
        "title": title,
        "location": location,
        "date_start": _dt(2026, 6, 1, 10, 0) if date_start is _UNSET else date_start,
        "date_end": _dt(2026, 6, 1, 11, 0) if date_end is _UNSET else date_end,
    }


def test_active_between_trigger_and_event_end():
    now = _dt(2026, 6, 1, 10, 30)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 1
    assert isinstance(results[0], CalEventReminder)
    assert results[0].title == "Test"
    assert results[0].location == "Room A"
    assert results[0].event_key == "evt-key"


def test_not_active_before_trigger():
    now = _dt(2026, 6, 1, 9, 30)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 0


def test_not_active_after_event_end():
    now = _dt(2026, 6, 1, 12, 0)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 0


def test_active_at_exact_trigger_time():
    now = _dt(2026, 6, 1, 9, 45)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 1


def test_recurring_event_active_occurrence():
    master = _make_event(
        date_start=_dt(2026, 6, 1, 10, 0),
        date_end=_dt(2026, 6, 1, 11, 0),
        recurrence_rule=CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, interval=1),
    )
    now = _dt(2026, 6, 2, 10, 30)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45), is_recurring=True)],
        events_by_key={"evt-key": master},
        now=now,
    )
    assert len(results) == 1
    assert results[0].date_start == _dt(2026, 6, 2, 10, 0)


def test_recurring_event_not_active_between_occurrences():
    master = _make_event(
        date_start=_dt(2026, 6, 1, 10, 0),
        date_end=_dt(2026, 6, 1, 11, 0),
        recurrence_rule=CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, interval=1),
    )
    now = _dt(2026, 6, 1, 14, 0)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45), is_recurring=True)],
        events_by_key={"evt-key": master},
        now=now,
    )
    assert len(results) == 0


def test_event_missing_skipped():
    now = _dt(2026, 6, 2, 10, 30)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={},
        now=now,
    )
    assert len(results) == 0


def test_lookahead_extends_active_window():
    now = _dt(2026, 6, 1, 11, 20)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 0
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45))],
        events_by_key={"evt-key": _make_event()},
        now=now,
        lookahead_minutes=30,
    )
    assert len(results) == 1


def test_no_date_end_reminder_stays_active():
    now = _dt(2026, 6, 1, 23, 0)
    results = ReminderEngine().compute_active(
        reminder_rows=[_row(trigger_at=_dt(2026, 6, 1, 9, 45), date_end=None)],
        events_by_key={"evt-key": _make_event()},
        now=now,
    )
    assert len(results) == 1
