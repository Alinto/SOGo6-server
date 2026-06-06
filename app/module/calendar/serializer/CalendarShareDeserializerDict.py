from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalendarShare import CalendarShare
from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.utils.serializer.Deserializer import Deserializer


class CalendarShareDeserializerDict(Deserializer[dict[str, Any], CalendarShare]):
    """Deserializes a dict (from JSON) into a CalendarShare model."""

    def deserialize(self, data: dict[str, Any]) -> CalendarShare:
        return CalendarShare(
            user_uid=data["user_uid"],
            calendar_key=data["calendar_key"],
            public_level=CalendarShareLevel[data.get("public_level", "none").upper()],
            confidential_level=CalendarShareLevel[data.get("confidential_level", "none").upper()],
            private_level=CalendarShareLevel[data.get("private_level", "none").upper()],
            can_create=data.get("can_create", False),
            can_delete=data.get("can_delete", False),
        )
