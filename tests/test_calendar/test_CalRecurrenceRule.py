"""Unit tests for CalRecurrenceRule.to_dict()."""
from datetime import datetime, timezone

import pytest

from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency

_UTC = timezone.utc


@pytest.fixture
def daily():
    return CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY)


def test_frequency_value(daily):
    assert daily.to_dict()["frequency"] == "daily"


def test_interval_default(daily):
    assert daily.to_dict()["interval"] == 1


def test_until():
    dt = datetime(2026, 12, 31, 0, 0, 0, tzinfo=_UTC)
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, until=dt)
    assert rule.to_dict()["until"] == dt.isoformat()


def test_set_fields_included_with_their_values():
    rule = CalRecurrenceRule(
        frequency=RecurrenceFrequency.WEEKLY, interval=2, count=10,
        by_day=["MO", "WE", "FR"], by_month_day=[1, 15], by_month=[3, 9],
    )
    d = rule.to_dict()
    assert d["interval"] == 2
    assert d["count"] == 10
    assert d["by_day"] == ["MO", "WE", "FR"]
    assert d["by_month_day"] == [1, 15]
    assert d["by_month"] == [3, 9]


def test_week_start_omitted_when_mo(daily):
    assert "week_start" not in daily.to_dict()


def test_week_start_included_when_not_mo():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, week_start="SU")
    assert rule.to_dict()["week_start"] == "SU"


def test_optional_fields_absent_when_none(daily):
    d = daily.to_dict()
    for key in ("until", "count", "by_day", "by_month_day", "by_month",
                "by_year_day", "by_week_no", "by_set_pos", "by_hour",
                "by_minute", "by_second", "week_start"):
        assert key not in d


