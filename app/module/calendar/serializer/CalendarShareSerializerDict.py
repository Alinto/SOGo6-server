from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalendarShare import CalendarShare
from app.module.calendar.serializer.CalendarPermissionsSerializerDict import CalendarPermissionsSerializerDict
from app.module.calendar.serializer.Serializer import Serializer


class CalendarShareSerializerDict(Serializer[CalendarShare, dict[str, Any]]):
    """Serializes CalendarShare to a dict (JSON-ready for storage or API)."""

    def __init__(self) -> None:
        self._permissions_serializer: CalendarPermissionsSerializerDict = CalendarPermissionsSerializerDict()

    def serialize(self, data: CalendarShare) -> dict[str, Any]:
        # A CalendarShare is a CalendarPermissions, so the permissions part is delegated as-is.
        result: dict[str, Any] = self._permissions_serializer.serialize(data)
        result["user_uid"] = data.user_uid
        result["calendar_key"] = data.calendar_key
        return result
