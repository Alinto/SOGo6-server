from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalReminder import CalReminder
from app.utils.serializer.Serializer import Serializer


class CalReminderSerializerDict(Serializer[CalReminder, dict[str, Any]]):
    """Serializes a CalReminder (RFC 5545 VALARM) to a dict."""

    def serialize(self, data: CalReminder) -> dict[str, Any]:
        """Convert a CalReminder to its dict representation."""
        return {"method": data.method.value, "minutes_before": data.minutes_before}
