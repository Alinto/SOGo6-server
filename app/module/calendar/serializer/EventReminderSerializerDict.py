from __future__ import annotations

from typing import Any

from app.utils.datetime.DateTimeUtils import apply_tz, fmt_dt
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.utils.serializer.Serializer import Serializer


class EventReminderSerializerDict(Serializer[CalEventReminder, dict[str, Any]]):
    """Serializes a CalEventReminder to a dict for API responses."""

    def serialize(self, data: CalEventReminder) -> dict[str, Any]:
        return {
            "event_key": data.event_key,
            "title": data.title,
            "location": data.location,
            "date_start": fmt_dt(data.date_start) if data.date_start else None,
            "date_end": fmt_dt(data.date_end) if data.date_end else None,
            "method": data.method.value,
            "minutes_before": data.minutes_before,
            "trigger_at": fmt_dt(data.trigger_at),
            "dates_with_tz": self._dates_with_tz(data),
        }

    @staticmethod
    def _dates_with_tz(data: CalEventReminder) -> dict[str, str | None]:
        event_tz = data.timezone
        cal_tz = data.calendar_timezone
        return {
            "date_start_tz_event": apply_tz(data.date_start, event_tz) if event_tz and data.date_start else None,
            "date_end_tz_event": apply_tz(data.date_end, event_tz) if event_tz and data.date_end else None,
            "trigger_at_tz_event": apply_tz(data.trigger_at, event_tz) if event_tz else None,
            "date_start_tz_calendar": apply_tz(data.date_start, cal_tz) if cal_tz and data.date_start else None,
            "date_end_tz_calendar": apply_tz(data.date_end, cal_tz) if cal_tz and data.date_end else None,
            "trigger_at_tz_calendar": apply_tz(data.trigger_at, cal_tz) if cal_tz else None,
        }
