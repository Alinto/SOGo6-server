from __future__ import annotations

from typing import Any

from app.factory.share.shareCalendar import STR_TO_LEVEL
from app.module.calendar.model.CalendarShare import CalendarShare
from app.utils.serializer.Deserializer import Deserializer


class CalendarShareDeserializerDict(Deserializer[dict[str, Any], CalendarShare]):
    """Deserializes a dict (from JSON) into a CalendarShare model."""

    def deserialize(self, data: dict[str, Any]) -> CalendarShare:
        return CalendarShare(
            user_uid=data["user_uid"],
            calendar_key=data["calendar_key"],
            public_level=STR_TO_LEVEL[data.get("public", "none")],
            confidential_level=STR_TO_LEVEL[data.get("confidential", "none")],
            private_level=STR_TO_LEVEL[data.get("private", "none")],
            can_create=data.get("can_create_objects", False),
            can_delete=data.get("can_erase_objects", False),
        )
