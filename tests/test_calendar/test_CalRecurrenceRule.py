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


def test_interval_custom():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, interval=2)
    assert rule.to_dict()["interval"] == 2


def test_until():
    dt = datetime(2026, 12, 31, 0, 0, 0, tzinfo=_UTC)
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, until=dt)
    assert rule.to_dict()["until"] == dt.isoformat()


def test_count():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.DAILY, count=10)
    assert rule.to_dict()["count"] == 10


def test_by_day():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.WEEKLY, by_day=["MO", "WE", "FR"])
    assert rule.to_dict()["by_day"] == ["MO", "WE", "FR"]


def test_by_month_day():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.MONTHLY, by_month_day=[1, 15])
    assert rule.to_dict()["by_month_day"] == [1, 15]


def test_by_month():
    rule = CalRecurrenceRule(frequency=RecurrenceFrequency.YEARLY, by_month=[3, 9])
    assert rule.to_dict()["by_month"] == [3, 9]


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


def test_all_freq_values():
    for freq in RecurrenceFrequency:
        rule = CalRecurrenceRule(frequency=freq)
        assert rule.to_dict()["frequency"] == freq.value


