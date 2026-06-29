from __future__ import annotations

import dataclasses
from typing import Any

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.serializer.CalCalendarDeserializer import CalCalendarDeserializer


class CalCalendarDeserializerDict(CalCalendarDeserializer[dict]):
    """Deserializes plain dicts into CalCalendar objects.

    Used for both creation (full dict) and update (partial dict). The owner uid, opaque key and
    backend source_type are not caller-supplied: they are set by the module / interface. The only
    field needing coercion is default_type (CLASS string -> EventVisibility).
    """

    def deserialize(self, data: dict[str, Any]) -> CalCalendar:
        """Convert a dict into a CalCalendar. Absent fields keep the dataclass default."""
        return CalCalendar(
            user_uid="",
            name=data["name"],
            color=data.get("color"),
            description=data.get("description"),
            timezone=data.get("timezone") or "UTC",
            is_default=data.get("is_default", False),
            include_in_freebusy=data.get("include_in_freebusy", True),
            default_event_duration_min=data.get("default_event_duration_min"),
            default_alarm_duration_min=data.get("default_alarm_duration_min"),
            default_type=self._parse_default_type(data.get("default_type")),
        )

    def deserialize_with_update(self, origin: CalCalendar, update: dict | CalCalendar) -> CalCalendar:
        """Apply a partial update to a copy of origin and return it.

        When update is a dict, default_type is coerced to its enum and the model's apply_update gates
        which fields are mutable, so unknown or immutable keys are ignored. When update is already a
        CalCalendar, return it directly.
        """
        if isinstance(update, CalCalendar):
            return update

        merged: CalCalendar = dataclasses.replace(origin)
        normalized: dict[str, Any] = dict(update)
        if "default_type" in normalized:
            normalized["default_type"] = self._parse_default_type(normalized["default_type"])
        merged.apply_update(normalized)
        return merged

    @staticmethod
    def _parse_default_type(value: str | None) -> EventVisibility | None:
        """Parse the default visibility (RFC 5545 CLASS); None stays None (use the global default)."""
        return EventVisibility(value) if value else None
