"""Unit tests for CalEvent model."""
from datetime import datetime, timedelta, timezone

import pytest

from app.module.calendar.CalendarConst import (DEFAULT_REMINDER_MINUTES, MAX_EVENT_ALL_DAY_DURATION_HOURS,
                                               MAX_EVENT_DURATION_HOURS)
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.utils.exceptions import RequestException

_UTC = timezone.utc


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _make_event(**kwargs):
    defaults = dict(
        uid="evt@example.com",
        title="Test",
        date_start=_dt(2026, 6, 1, 9),
        date_end=_dt(2026, 6, 1, 10),
    )
    defaults.update(kwargs)
    return CalEvent(**defaults)


# ========== validate ==========

def test_validate_ok():
    event = _make_event()
    event.validate()


def test_validate_exact_max_duration():
    event = _make_event(
        date_start=_dt(2026, 6, 1, 0),
        date_end=_dt(2026, 6, 1, 0) + timedelta(hours=MAX_EVENT_DURATION_HOURS),
    )
    event.validate()


def test_validate_exceeds_max_duration():
    event = _make_event(
        date_start=_dt(2026, 6, 1, 0),
        date_end=_dt(2026, 6, 1, 0) + timedelta(hours=MAX_EVENT_DURATION_HOURS, minutes=1),
    )
    with pytest.raises(RequestException):
        event.validate()


def test_validate_all_day_within_cap():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 5),
    )
    event.validate()


def test_validate_all_day_exact_max_duration():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_ALL_DAY_DURATION_HOURS),
    )
    event.validate()


def test_validate_all_day_exceeds_max_duration():
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_ALL_DAY_DURATION_HOURS, minutes=1),
    )
    with pytest.raises(RequestException):
        event.validate()


def test_validate_all_day_exceeds_uses_all_day_cap_not_default():
    # Duration > MAX_EVENT_DURATION_HOURS but < MAX_EVENT_ALL_DAY_DURATION_HOURS:
    # passes only because the all_day branch applies a higher cap.
    assert MAX_EVENT_ALL_DAY_DURATION_HOURS > MAX_EVENT_DURATION_HOURS
    event = _make_event(
        all_day=True,
        date_start=_dt(2026, 6, 1),
        date_end=_dt(2026, 6, 1) + timedelta(hours=MAX_EVENT_DURATION_HOURS + 1),
    )
    event.validate()


def test_validate_no_dates():
    event = _make_event(date_start=None, date_end=None)
    event.validate()


# ========== is_organized_by ==========

def test_is_organized_by_matches():
    event = _make_event(organizer=CalOrganizer(email="bob@example.com"))
    assert event.is_organized_by("bob@example.com") is True
    assert event.is_organized_by("alice@example.com") is False


def test_is_organized_by_false_without_organizer():
    event = _make_event(organizer=None)
    assert event.is_organized_by("bob@example.com") is False


# ========== is_attending ==========

def _att(email, status):
    return CalAttendee(email=email, status=status)


def test_is_attending_personal_event_without_attendees():
    event = _make_event()
    assert event.is_attending("bob@example.com") is True


def test_is_attending_accepted_or_tentative():
    event = _make_event(attendees=[
        _att("acc@example.com", AttendeeStatus.ACCEPTED),
        _att("tent@example.com", AttendeeStatus.TENTATIVE),
    ])
    assert event.is_attending("acc@example.com") is True
    assert event.is_attending("tent@example.com") is True


def test_is_attending_false_for_declined_or_needs_action():
    event = _make_event(attendees=[
        _att("dec@example.com", AttendeeStatus.DECLINED),
        _att("na@example.com", AttendeeStatus.NEEDS_ACTION),
    ])
    assert event.is_attending("dec@example.com") is False
    assert event.is_attending("na@example.com") is False


def test_is_attending_true_for_non_attendee_identity():
    event = _make_event(attendees=[_att("someone@example.com", AttendeeStatus.DECLINED)])
    assert event.is_attending("organizer@example.com") is True


# ========== set_attendance ==========

def test_set_attendance_updates_matching_attendee():
    event = _make_event(attendees=[_att("bob@example.com", AttendeeStatus.NEEDS_ACTION)])
    assert event.set_attendance("bob@example.com", AttendeeStatus.ACCEPTED) is True
    assert event.attendees[0].status == AttendeeStatus.ACCEPTED


def test_set_attendance_returns_false_when_not_an_attendee():
    event = _make_event(attendees=[_att("bob@example.com", AttendeeStatus.NEEDS_ACTION)])
    assert event.set_attendance("someone@example.com", AttendeeStatus.ACCEPTED) is False
    assert event.attendees[0].status == AttendeeStatus.NEEDS_ACTION


# ========== has_scheduling_changes ==========

def test_has_scheduling_changes_on_move():
    event = _make_event()
    moved = _make_event(date_start=_dt(2026, 6, 2, 9), date_end=_dt(2026, 6, 2, 10))
    assert event.has_scheduling_changes(moved) is True


def test_has_scheduling_changes_false_for_cosmetic_edit():
    event = _make_event(title="Old")
    renamed = _make_event(title="New")
    assert event.has_scheduling_changes(renamed) is False


# ========== reset_attendee_responses ==========

def test_reset_attendee_responses_resets_attendees_but_not_organizer():
    event = _make_event(
        organizer=CalOrganizer(email="boss@example.com"),
        attendees=[
            _att("boss@example.com", AttendeeStatus.ACCEPTED),
            _att("bob@example.com", AttendeeStatus.ACCEPTED),
        ],
    )
    event.reset_attendee_responses()
    by_email = {a.email: a for a in event.attendees}
    assert by_email["bob@example.com"].status == AttendeeStatus.NEEDS_ACTION
    assert by_email["bob@example.com"].rsvp is True
    assert by_email["boss@example.com"].status == AttendeeStatus.ACCEPTED


# ========== apply_defaults - calendar-level defaults ==========

def test_apply_defaults_visibility_uses_calendar_default():
    event = _make_event()
    event.apply_defaults(default_visibility=EventVisibility.PRIVATE)
    assert event.visibility == EventVisibility.PRIVATE


def test_apply_defaults_visibility_global_fallback_public():
    event = _make_event()
    event.apply_defaults()
    assert event.visibility == EventVisibility.PUBLIC


def test_apply_defaults_visibility_keeps_explicit_value():
    event = _make_event(visibility=EventVisibility.CONFIDENTIAL)
    event.apply_defaults(default_visibility=EventVisibility.PRIVATE)
    assert event.visibility == EventVisibility.CONFIDENTIAL


def test_apply_defaults_duration_fills_missing_end():
    event = _make_event(date_start=_dt(2026, 6, 1, 9), date_end=None)
    event.apply_defaults(default_duration_min=30)
    assert event.date_end == _dt(2026, 6, 1, 9) + timedelta(minutes=30)


def test_apply_defaults_duration_skips_when_end_present():
    event = _make_event(date_start=_dt(2026, 6, 1, 9), date_end=_dt(2026, 6, 1, 10))
    event.apply_defaults(default_duration_min=30)
    assert event.date_end == _dt(2026, 6, 1, 10)


def test_apply_defaults_duration_skips_all_day():
    event = _make_event(date_start=_dt(2026, 6, 1), date_end=None, all_day=True)
    event.apply_defaults(default_duration_min=30)
    assert event.date_end is None


def test_apply_defaults_duration_skips_task():
    event = _make_event(date_start=_dt(2026, 6, 1, 9), date_end=None, component_type=ComponentType.TASK)
    event.apply_defaults(default_duration_min=30)
    assert event.date_end is None


# ========== resolve_reminder_offsets ==========

def test_resolve_reminder_offsets_uses_calendar_default():
    event = _make_event(reminders=[CalReminder(method=ReminderMethod.POPUP)])
    event.resolve_reminder_offsets(20)
    assert event.reminders[0].minutes_before == 20


def test_resolve_reminder_offsets_global_fallback():
    event = _make_event(reminders=[CalReminder(method=ReminderMethod.POPUP)])
    event.resolve_reminder_offsets(None)
    assert event.reminders[0].minutes_before == DEFAULT_REMINDER_MINUTES


def test_resolve_reminder_offsets_keeps_explicit_offset():
    event = _make_event(reminders=[CalReminder(method=ReminderMethod.POPUP, minutes_before=5)])
    event.resolve_reminder_offsets(20)
    assert event.reminders[0].minutes_before == 5


# ========== normalize_all_day ==========

def test_normalize_all_day_advances_zero_duration_end():
    start = _dt(2026, 4, 28)
    event = _make_event(all_day=True, date_start=start, date_end=start)
    event.normalize_all_day()
    assert event.date_end == _dt(2026, 4, 29)


def test_normalize_all_day_leaves_valid_end_untouched():
    event = _make_event(all_day=True, date_start=_dt(2026, 4, 28), date_end=_dt(2026, 4, 30))
    event.normalize_all_day()
    assert event.date_end == _dt(2026, 4, 30)


def test_normalize_all_day_ignores_timed_event():
    start = _dt(2026, 4, 28, 9)
    event = _make_event(all_day=False, date_start=start, date_end=start)
    event.normalize_all_day()
    assert event.date_end == start
