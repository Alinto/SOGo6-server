from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalendarShare import CalendarShare
from app.module.calendar.serializer.CalendarPermissionsSerializerDict import CalendarPermissionsSerializerDict


class CalendarShareSerializerDict(CalendarPermissionsSerializerDict):
    """Serializes CalendarShare to a dict (JSON-ready for storage or API)."""

    def serialize(self, data: CalendarShare) -> dict[str, Any]:
        result: dict[str, Any] = super().serialize(data)
        result["user_uid"] = data.user_uid
        result["calendar_key"] = data.calendar_key
        return result
