from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarPermissionsSerializerDict import CalendarPermissionsSerializerDict
from app.module.calendar.serializer.CalCalendarSerializer import CalCalendarSerializer


class CalCalendarSerializerDict(CalCalendarSerializer[dict]):
    """Converts a CalCalendar to a plain dict matching the SOGo6 REST API schema."""

    def __init__(self) -> None:
        self._permissions_serializer = CalendarPermissionsSerializerDict()

    def serialize(self, data: CalCalendar) -> dict[str, Any]:
        return {
            "key": data.key,
            "name": data.name,
            "color": data.color,
            "description": data.description,
            "timezone": data.timezone,
            "is_default": data.is_default,
            "source_type": data.source_type.value,
            "ctag": data.ctag,
            "include_in_freebusy": data.include_in_freebusy,
            "default_event_duration_min": data.default_event_duration_min,
            "default_alarm_duration_min": data.default_alarm_duration_min,
            "default_type": data.default_type.value if data.default_type else None,
            "permissions": self._permissions_serializer.serialize(data.permissions) if data.permissions else None,
        }
