"""
Unit tests for RruleEngine.

Covers: no RRULE, DAILY, WEEKLY+BYDAY, MONTHLY, YEARLY,
UNTIL, COUNT, EXDATE, RECURRENCE-ID override, RDATE,
SECONDLY, HOURLY, BYYEARDAY, BYWEEKNO.
All datetimes are UTC.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.rrule.RruleEngine import RruleEngine

_UTC = timezone.utc


def _dt(year, month, day, hour=9):
    return datetime(year, month, day, hour, tzinfo=_UTC)


def _master(dtstart, dtend, rule=None, exceptions=None):
    return CalEvent(
        uid="series@test",
        title="Recurring",
        date_start=dtstart,
        date_end=dtend,
        recurrence_rule=rule,
        recurrence_exceptions=exceptions or [],
    )


def _rule(freq, **kwargs):
    return CalRecurrenceRule(frequency=freq, **kwargs)


@pytest.fixture
def engine():
    return RruleEngine()


def test_no_rrule(engine):
    master = _master(_dt(2026, 1, 5), _dt(2026, 1, 5, 10))
    assert engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 31)) == [master]


# DAILY

def test_daily_basic(engine):
    master = _master(_dt(2026, 1, 5), _dt(2026, 1, 5, 10), rule=_rule(RecurrenceFrequency.DAILY))
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 9))
    starts = [e.date_start for e in result]
    assert len(result) == 5
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 1, 9) in starts


def test_daily_mid_series_window(engine):
    # Series starts Jan 1; window opens Jan 5 — occurrences Jan 1-4 must be absent.
    master = _master(_dt(2026, 1, 1), _dt(2026, 1, 1, 10), rule=_rule(RecurrenceFrequency.DAILY))
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 7))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 4) not in starts
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 1, 7) in starts
    assert len(result) == 3


def test_daily_until(engine):
    until = _dt(2026, 1, 7)
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY, until=until),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 31))
    assert all(e.date_start <= until for e in result)
    assert len(result) == 3  # Jan 5, 6, 7


def test_daily_count(engine):
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY, count=3),
    )
    assert len(engine.expand(master, _dt(2026, 1, 1), _dt(2026, 12, 31))) == 3


def test_out_of_range_empty(engine):
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY, count=3),
    )
    assert engine.expand(master, _dt(2026, 3, 1), _dt(2026, 3, 31)) == []


# WEEKLY

def test_weekly_byday(engine):
    # Jan 5 2026 = Monday. MO: Jan 5, 12 — WE: Jan 7, 14
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.WEEKLY, by_day=["MO", "WE"]),
    )
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 14))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 1, 7) in starts
    assert _dt(2026, 1, 12) in starts
    assert _dt(2026, 1, 14) in starts
    assert len(result) == 4


def test_weekly_no_byday(engine):
    # Jan 5 = Mon; should repeat every Monday.
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.WEEKLY),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 26))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 1, 12) in starts
    assert _dt(2026, 1, 19) in starts
    assert _dt(2026, 1, 26) in starts
    assert len(result) == 4


# MONTHLY

def test_monthly_same_day(engine):
    master = _master(
        _dt(2026, 1, 15), _dt(2026, 1, 15, 10),
        rule=_rule(RecurrenceFrequency.MONTHLY),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 4, 30))
    assert all(e.date_start.day == 15 for e in result)
    assert len(result) == 4


def test_monthly_bymonthday(engine):
    master = _master(
        _dt(2026, 1, 1), _dt(2026, 1, 1, 10),
        rule=_rule(RecurrenceFrequency.MONTHLY, by_month_day=[10]),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 3, 31))
    starts = [e.date_start for e in result]
    assert all(e.date_start.day == 10 for e in result)
    assert _dt(2026, 1, 10) in starts
    assert _dt(2026, 2, 10) in starts
    assert _dt(2026, 3, 10) in starts


def test_monthly_byday_positional(engine):
    # FREQ=MONTHLY;BYDAY=1MO → first Monday of each month.
    # First Monday Jan 2026 = Jan 5; Feb = Feb 2; Mar = Mar 2
    master = _master(
        _dt(2026, 1, 1), _dt(2026, 1, 1, 10),
        rule=_rule(RecurrenceFrequency.MONTHLY, by_day=["1MO"]),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 3, 31))
    starts = [e.date_start for e in result]
    assert all(e.date_start.weekday() == 0 for e in result)  # all Mondays
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 2, 2) in starts
    assert _dt(2026, 3, 2) in starts


# YEARLY

def test_yearly_basic(engine):
    master = _master(
        _dt(2026, 3, 15), _dt(2026, 3, 15, 10),
        rule=_rule(RecurrenceFrequency.YEARLY),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2028, 12, 31))
    starts = [e.date_start for e in result]
    assert _dt(2026, 3, 15) in starts
    assert _dt(2027, 3, 15) in starts
    assert _dt(2028, 3, 15) in starts
    assert len(result) == 3


# EXDATE

def test_exdate(engine):
    exc = _dt(2026, 1, 6)
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY),
        exceptions=[exc],
    )
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 7))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 6) not in starts
    assert _dt(2026, 1, 5) in starts
    assert _dt(2026, 1, 7) in starts


# RECURRENCE-ID override

def test_recurrence_id_override(engine):
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY),
    )
    # Jan 6 occurrence is moved to 14:00
    override = CalEvent(
        uid="series@test",
        title="Modified Jan 6",
        date_start=_dt(2026, 1, 6, 14),
        date_end=_dt(2026, 1, 6, 15),
        recurrence_id=_dt(2026, 1, 6),
    )
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 7), overrides=[override])
    jan6 = [e for e in result if e.date_start.date() == _dt(2026, 1, 6).date()]
    assert len(jan6) == 1
    assert jan6[0].title == "Modified Jan 6"
    assert jan6[0].date_start.hour == 14


# RDATE

def test_rdate(engine):
    rule = _rule(RecurrenceFrequency.DAILY, count=3)
    rule.additional_dates = [_dt(2026, 1, 20)]
    master = _master(_dt(2026, 1, 5), _dt(2026, 1, 5, 10), rule=rule)
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 31))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 20) in starts
    assert _dt(2026, 1, 5) in starts
    assert len(result) == 4  # 3 from COUNT + 1 RDATE


# Occurrence copy contract

def test_occurrence_copy_fields(engine):
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.DAILY, count=2),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 31))
    for occ in result:
        assert occ.recurrence_id == occ.date_start
        assert occ.recurrence_rule is None


def test_occurrence_inherits_master_fields(engine):
    master = CalEvent(
        uid="series@test",
        title="Team Standup",
        description="Daily sync",
        date_start=_dt(2026, 1, 5),
        date_end=_dt(2026, 1, 5, 10),
        recurrence_rule=_rule(RecurrenceFrequency.DAILY, count=1),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 1, 31))
    assert result[0].title == "Team Standup"
    assert result[0].description == "Daily sync"


# SECONDLY / MINUTELY / HOURLY

def test_secondly(engine):
    dtstart = datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC)
    master = CalEvent(
        uid="s@test", title="T",
        date_start=dtstart,
        date_end=datetime(2026, 1, 5, 9, 0, 10, tzinfo=_UTC),
        recurrence_rule=CalRecurrenceRule(
            frequency=RecurrenceFrequency.SECONDLY, interval=30, count=3
        ),
    )
    result = engine.expand(master, datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 12, 31, tzinfo=_UTC))
    assert len(result) == 3
    assert result[0].date_start == datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC)
    assert result[1].date_start == datetime(2026, 1, 5, 9, 0, 30, tzinfo=_UTC)
    assert result[2].date_start == datetime(2026, 1, 5, 9, 1, 0, tzinfo=_UTC)


def test_hourly(engine):
    master = _master(
        _dt(2026, 1, 5, 9), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.HOURLY, count=4),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2026, 12, 31))
    assert len(result) == 4
    assert result[0].date_start == _dt(2026, 1, 5, 9)
    assert result[1].date_start == _dt(2026, 1, 5, 10)
    assert result[2].date_start == _dt(2026, 1, 5, 11)
    assert result[3].date_start == _dt(2026, 1, 5, 12)


# BYYEARDAY

def test_byyearday_positive(engine):
    # BYYEARDAY=100: Jan(31)+Feb(28)+Mar(31)+10 = 100 → April 10 in non-leap years.
    master = _master(
        _dt(2026, 1, 1), _dt(2026, 1, 1, 10),
        rule=_rule(RecurrenceFrequency.YEARLY, by_year_day=[100]),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2027, 12, 31))
    starts = [e.date_start for e in result]
    assert _dt(2026, 4, 10) in starts
    assert _dt(2027, 4, 10) in starts
    assert len(result) == 2


def test_byyearday_negative(engine):
    # BYYEARDAY=-1 → last day of year (Dec 31).
    master = _master(
        _dt(2026, 1, 1), _dt(2026, 1, 1, 10),
        rule=_rule(RecurrenceFrequency.YEARLY, by_year_day=[-1]),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2027, 12, 31))
    assert all(e.date_start.month == 12 and e.date_start.day == 31 for e in result)
    assert len(result) == 2


# BYWEEKNO

def test_byweekno(engine):
    # FREQ=YEARLY;BYWEEKNO=2 with dtstart on a Monday.
    # ISO week 2 of 2026 starts Jan 5 (Mon); week 2 of 2027 starts Jan 11 (Mon).
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.YEARLY, by_week_no=[2]),
    )
    result = engine.expand(master, _dt(2026, 1, 1), _dt(2027, 12, 31))
    starts = [e.date_start for e in result]
    assert _dt(2026, 1, 5) in starts
    assert datetime(2027, 1, 11, 9, tzinfo=_UTC) in starts
    assert len(result) == 2


# BYHOUR / BYMINUTE / BYSECOND

def test_daily_byhour_expands_multiple_times_per_day(engine):
    # FREQ=DAILY;BYHOUR=9,14 → 2 occurrences per day at 09:00 and 14:00.
    master = _master(
        datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC),
        datetime(2026, 1, 5, 10, 0, 0, tzinfo=_UTC),
        rule=_rule(RecurrenceFrequency.DAILY, by_hour=[9, 14], count=4),
    )
    result = engine.expand(master, datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 12, 31, tzinfo=_UTC))
    starts = [e.date_start for e in result]
    assert len(result) == 4
    assert datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC) in starts
    assert datetime(2026, 1, 5, 14, 0, 0, tzinfo=_UTC) in starts
    assert datetime(2026, 1, 6, 9, 0, 0, tzinfo=_UTC) in starts
    assert datetime(2026, 1, 6, 14, 0, 0, tzinfo=_UTC) in starts


def test_hourly_byminute_filters_minutes(engine):
    # FREQ=HOURLY;BYMINUTE=0;COUNT=3 → only at :00 of each hour.
    master = _master(
        datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC),
        datetime(2026, 1, 5, 9, 30, 0, tzinfo=_UTC),
        rule=_rule(RecurrenceFrequency.HOURLY, by_minute=[0], count=3),
    )
    result = engine.expand(master, datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 12, 31, tzinfo=_UTC))
    assert len(result) == 3
    assert all(e.date_start.minute == 0 for e in result)
    assert result[1].date_start == datetime(2026, 1, 5, 10, 0, 0, tzinfo=_UTC)


# BYSETPOS in DAILY / WEEKLY

def test_daily_byhour_bysetpos_selects_last_per_day(engine):
    # FREQ=DAILY;BYHOUR=9,12,17;BYSETPOS=-1 → only 17:00 each day.
    master = _master(
        datetime(2026, 1, 5, 9, 0, 0, tzinfo=_UTC),
        datetime(2026, 1, 5, 10, 0, 0, tzinfo=_UTC),
        rule=_rule(RecurrenceFrequency.DAILY, by_hour=[9, 12, 17], by_set_pos=[-1], count=3),
    )
    result = engine.expand(master, datetime(2026, 1, 1, tzinfo=_UTC), datetime(2026, 12, 31, tzinfo=_UTC))
    assert len(result) == 3
    assert all(e.date_start.hour == 17 for e in result)


def test_weekly_byday_bysetpos_selects_first_per_week(engine):
    # FREQ=WEEKLY;BYDAY=MO,WE,FR;BYSETPOS=1 → only Monday each week.
    # Jan 5 2026 = Monday.
    master = _master(
        _dt(2026, 1, 5), _dt(2026, 1, 5, 10),
        rule=_rule(RecurrenceFrequency.WEEKLY, by_day=["MO", "WE", "FR"], by_set_pos=[1]),
    )
    result = engine.expand(master, _dt(2026, 1, 5), _dt(2026, 1, 26))
    assert all(e.date_start.weekday() == 0 for e in result)  # all Mondays
    assert len(result) == 4


# ========== Tests for get_min_date / get_max_date ==========


def test_get_min_date_returns_date_start(engine):
    master = _master(_dt(2026, 3, 10), _dt(2026, 3, 10, 10))
    assert engine.get_min_date(master) == master.date_start


def test_get_max_date_no_rrule(engine):
    master = _master(_dt(2026, 3, 10), _dt(2026, 3, 10, 10))
    assert engine.get_max_date(master) == master.date_end


def test_get_max_date_infinite(engine):
    # No UNTIL, no COUNT → unbounded series.
    master = _master(
        _dt(2026, 3, 10), _dt(2026, 3, 10, 10),
        rule=_rule(RecurrenceFrequency.WEEKLY),
    )
    assert engine.get_max_date(master) is None


def test_get_max_date_count(engine):
    # FREQ=DAILY;COUNT=3 starting March 10 → last occurrence March 12.
    master = _master(
        _dt(2026, 3, 10), _dt(2026, 3, 10, 10),
        rule=_rule(RecurrenceFrequency.DAILY, count=3),
    )
    assert engine.get_max_date(master) == _dt(2026, 3, 12, 10)


def test_get_max_date_until_last_occurrence_before_until(engine):
    # FREQ=WEEKLY;BYDAY=MO;UNTIL=2026-03-26 (a Thursday).
    # Mar 9 = Monday. Mondays: Mar 9, 16, 23 → last start = Mar 23, last end = Mar 23 10:00.
    until = datetime(2026, 3, 26, 23, 59, 59, tzinfo=_UTC)
    master = _master(
        _dt(2026, 3, 9), _dt(2026, 3, 9, 10),
        rule=_rule(RecurrenceFrequency.WEEKLY, by_day=["MO"], until=until),
    )
    assert engine.get_max_date(master) == _dt(2026, 3, 23, 10)
