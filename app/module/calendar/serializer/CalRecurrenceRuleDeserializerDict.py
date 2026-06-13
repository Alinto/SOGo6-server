from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.utils.serializer.Deserializer import Deserializer


class CalRecurrenceRuleDeserializerDict(Deserializer[dict[str, Any], CalRecurrenceRule]):
    """Deserializes a dict into a CalRecurrenceRule (RFC 5545 RRULE)."""

    def deserialize(self, data: dict[str, Any]) -> CalRecurrenceRule:
        """Convert a dict into a CalRecurrenceRule."""
        return CalRecurrenceRule(
            frequency=RecurrenceFrequency(data["frequency"]),
            interval=data.get("interval", 1),
            until=self._parse_dt_opt(data.get("until")),
            count=data.get("count"),
            by_day=data.get("by_day"),
            by_month_day=data.get("by_month_day"),
            by_month=data.get("by_month"),
            by_year_day=data.get("by_year_day"),
            by_week_no=data.get("by_week_no"),
            by_set_pos=data.get("by_set_pos"),
            by_hour=data.get("by_hour"),
            by_minute=data.get("by_minute"),
            by_second=data.get("by_second"),
            week_start=data.get("week_start", "MO"),
        )

    @staticmethod
    def _parse_dt_opt(value: str | None) -> datetime | None:
        """Parse an optional ISO 8601 UTC datetime string; return None when absent."""
        return datetime.fromisoformat(value).astimezone(timezone.utc) if value else None
