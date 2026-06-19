from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.utils.serializer.Deserializer import Deserializer


class CalReminderDeserializerDict(Deserializer[dict[str, Any], CalReminder]):
    """Deserializes a dict into a CalReminder (RFC 5545 VALARM)."""

    def deserialize(self, data: dict[str, Any]) -> CalReminder:
        """Convert a dict into a CalReminder.

        minutes_before is left as None when the caller omits it: the module resolves it from the
        parent calendar's default_alarm_duration_min (or the global fallback) before persisting.
        """
        return CalReminder(
            method=ReminderMethod(data.get("method", ReminderMethod.POPUP.value)),
            minutes_before=data.get("minutes_before"),
        )
