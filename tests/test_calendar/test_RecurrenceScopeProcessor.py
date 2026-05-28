from datetime import datetime, timedelta, timezone

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction, RecurrenceScopeProcessor
from app.module.calendar.source.CalendarSource import CalendarSource

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="master@example.com",
        title="Daily Standup",
        date_start=_dt(2026, 6, 1, 9),
        date_end=_dt(2026, 6, 1, 10),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


def _merge_update(master, **kwargs):
    """Simulate deserialize_with_update: copy master and apply kwargs on top."""
    import dataclasses
    return dataclasses.replace(master, **kwargs)


def _daily_rule(count=5):
    return CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, interval=1, count=count)


def _monthly_rule(count=6):
    return CalRecurrenceRule(frequency=RecurrenceFrequency.MONTHLY, interval=1, by_month_day=[1], count=count)


class FakeSource(CalendarSource):
    """Minimal CalendarSource that tracks insert/split calls without a database."""

    def __init__(self):
        cal = CalCalendar(key="cal-key", user_uid="user@example.com", name="Test", ctag=0)
        super().__init__(cal)
        self.inserted = []
        self.updated = []
        self.split_calls = []
        self._events_by_uid = {}

    def _fetch_events(self, start, end, search=None):
        return []

    def is_writable(self):
        return True

    def insert_event(self, event):
        event.key = event.key or "new-key"
        event.db_id = 1
        self.inserted.append(event)
        self._events_by_uid[event.uid] = event
        return event

    def split_event(self, uid, until, from_dt):
        self.split_calls.append((uid, until, from_dt))
        master = self._events_by_uid.get(uid)
        if master is not None:
            return [(master, EventAction.UPDATE)]
        return []

    def update_event(self, event):
        self.updated.append(event)
        if event.uid:
            self._events_by_uid[event.uid] = event

    def get_master_event_by_uid(self, uid):
        return self._events_by_uid.get(uid)


# ========== process — dispatch ==========

def test_process_standard_update():
    master = _make_event(key="evt-key", sequence=2)
    update = _merge_update(master, title="Updated Title")
    source = FakeSource()
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert scope_result.result.title == "Updated Title"
    assert scope_result.result.sequence == 3
    assert len(scope_result.touched) == 1
    assert scope_result.touched[0][1] == EventAction.UPDATE
    assert len(source.inserted) == 0
    assert len(source.updated) == 1


def test_process_dispatches_to_split_occurrence():
    master = _make_event(key="evt-key", recurrence_rule=_daily_rule())
    update = _merge_update(master, recurrence_id=_dt(2026, 6, 3, 9), title="Override")
    source = FakeSource()
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert scope_result.result.recurrence_id == _dt(2026, 6, 3, 9)
    assert len(scope_result.touched) == 1
    assert scope_result.touched[0][1] == EventAction.INSERT
    assert len(source.inserted) == 1


def test_process_dispatches_to_split_series():
    master = _make_event(key="evt-key", recurrence_rule=_daily_rule())
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
        title="New Series",
    )
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert len(source.split_calls) == 1
    assert len(source.inserted) == 1
    assert scope_result.result.title == "New Series"
    actions = [action for _, action in scope_result.touched]
    assert EventAction.UPDATE in actions
    assert EventAction.INSERT in actions


# ========== split_occurrence ==========

def test_split_occurrence_creates_detached_row():
    master = _make_event(key="evt-key", recurrence_rule=_daily_rule())
    update = _merge_update(master, recurrence_id=_dt(2026, 6, 3, 9), title="Override June 3")
    source = FakeSource()
    result = RecurrenceScopeProcessor.split_occurrence(source, master, update)
    assert result.recurrence_id == _dt(2026, 6, 3, 9)
    assert result.title == "Override June 3"
    assert result.recurrence_rule is None
    assert result.key is not None
    assert result.db_id is not None
    assert result.sequence == 0


def test_split_occurrence_preserves_master_duration():
    master = _make_event(date_start=_dt(2026, 6, 1, 9), date_end=_dt(2026, 6, 1, 11), recurrence_rule=_daily_rule())
    update = _merge_update(master, recurrence_id=_dt(2026, 6, 3, 9))
    source = FakeSource()
    result = RecurrenceScopeProcessor.split_occurrence(source, master, update)
    assert result.date_end - result.date_start == timedelta(hours=2)


def test_split_occurrence_does_not_modify_master():
    master = _make_event(key="evt-key", title="Original", recurrence_rule=_daily_rule())
    update = _merge_update(master, recurrence_id=_dt(2026, 6, 3, 9), title="Override")
    source = FakeSource()
    RecurrenceScopeProcessor.split_occurrence(source, master, update)
    assert master.title == "Original"
    assert master.recurrence_rule is not None


def test_split_occurrence_inherits_uid():
    master = _make_event(uid="master-uid@example.com", recurrence_rule=_daily_rule())
    update = _merge_update(master, recurrence_id=_dt(2026, 6, 3, 9))
    source = FakeSource()
    result = RecurrenceScopeProcessor.split_occurrence(source, master, update)
    assert result.uid == "master-uid@example.com"


# ========== split_series ==========

def test_split_series_truncates_original():
    """process() dispatches split_event on the source before creating the new master."""
    master = _make_event(key="evt-key", uid="m@e.com", recurrence_rule=_daily_rule())
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
        title="New",
    )
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert len(source.split_calls) == 1
    uid, until, from_dt = source.split_calls[0]
    assert uid == "m@e.com"
    assert until == _dt(2026, 6, 3, 9) - timedelta(seconds=1)
    assert from_dt == _dt(2026, 6, 3, 9)
    assert scope_result.result.title == "New"


def test_split_series_creates_new_master():
    master = _make_event(recurrence_rule=_daily_rule())
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
        title="New Series",
    )
    result = RecurrenceScopeProcessor.split_series(source, master, update)
    assert result.title == "New Series"
    assert result.uid != master.uid
    assert result.uid_parent_split == master.uid
    assert result.date_start == _dt(2026, 6, 3, 9)
    assert result.sequence == 0
    assert result.key is not None


def test_split_series_truncate_only():
    """No content changes via process() → no new master, returns truncated original."""
    master = _make_event(key="evt-key", uid="m@e.com", recurrence_rule=_daily_rule())
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
    )
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert scope_result.result.uid == master.uid
    assert len(source.inserted) == 0
    assert len(source.split_calls) == 1
    actions = [action for _, action in scope_result.touched]
    assert EventAction.INSERT not in actions


def test_split_series_converts_count_to_until():
    """New series inherits COUNT from master but must convert it to UNTIL."""
    master = _make_event(
        recurrence_rule=_monthly_rule(count=6),
        date_start=_dt(2026, 6, 1, 10),
        date_end=_dt(2026, 6, 1, 11),
    )
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 9, 1, 10),
        recurrence_range="THISANDFUTURE",
        title="New Monthly",
    )
    result = RecurrenceScopeProcessor.split_series(source, master, update)
    assert result.recurrence_rule is not None
    assert result.recurrence_rule.count is None
    assert result.recurrence_rule.until is not None


def test_split_series_new_master_has_no_parent_uid():
    master = _make_event(recurrence_rule=_daily_rule(), parent_uid="should-be-cleared")
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
        title="X",
    )
    result = RecurrenceScopeProcessor.split_series(source, master, update)
    assert result.parent_uid is None


def test_split_series_clears_reminders_on_new_master():
    reminder = CalReminder(method=ReminderMethod.POPUP, minutes_before=15)
    master = _make_event(recurrence_rule=_daily_rule(), reminders=[reminder])
    source = FakeSource()
    source._events_by_uid[master.uid] = master
    update = _merge_update(master,
        recurrence_id=_dt(2026, 6, 3, 9),
        recurrence_range="THISANDFUTURE",
        title="X",
    )
    result = RecurrenceScopeProcessor.split_series(source, master, update)
    assert result.reminders == []


# ========== _normalize_all_day ==========

def test_allday_normalizes_zero_duration():
    master = _make_event(key="k", all_day=True, date_start=_dt(2026, 4, 28), date_end=_dt(2026, 4, 28))
    update = _merge_update(master, title="X")
    source = FakeSource()
    scope_result = RecurrenceScopeProcessor.process(source, master, update)
    assert scope_result.result.date_end == _dt(2026, 4, 29)
