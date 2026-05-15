from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarSerializer import CalendarSerializer


class CalendarSerializerDict(CalendarSerializer[dict]):
    """Converts a CalCalendar to a plain dict matching the SOGo6 REST API schema."""

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
        }
