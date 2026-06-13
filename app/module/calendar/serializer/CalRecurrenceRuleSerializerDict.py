from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.utils.calendar.DateTimeUtils import fmt_dt
from app.utils.serializer.Serializer import Serializer


class CalRecurrenceRuleSerializerDict(Serializer[CalRecurrenceRule, dict[str, Any]]):
    """Serializes a CalRecurrenceRule (RFC 5545 RRULE) to a dict."""

    def serialize(self, data: CalRecurrenceRule) -> dict[str, Any]:
        """Convert a CalRecurrenceRule to its dict representation."""
        return {
            "frequency": data.frequency.value,
            "interval": data.interval,
            "until": fmt_dt(data.until) if data.until else None,
            "count": data.count,
            "by_day": data.by_day,
            "by_month_day": data.by_month_day,
            "by_month": data.by_month,
            "by_year_day": data.by_year_day,
            "by_week_no": data.by_week_no,
            "by_set_pos": data.by_set_pos,
            "by_hour": data.by_hour,
            "by_minute": data.by_minute,
            "by_second": data.by_second,
            "week_start": data.week_start,
        }
