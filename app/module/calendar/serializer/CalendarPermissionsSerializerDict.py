from __future__ import annotations

from typing import Any

from app.factory.share.shareCalendar import LEVEL_TO_STR
from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.model.enums.CalendarShareLevel import CalendarShareLevel
from app.utils.serializer.Serializer import Serializer


class CalendarPermissionsSerializerDict(Serializer[CalendarPermissions, dict[str, Any]]):
    """Serializes CalendarPermissions to the API ``rights`` dict.

    Same shape and level strings as the sharing API (CalendarShareRightsSchema), which is also
    the blob stored in sogo6_acl.
    """

    def serialize(self, data: CalendarPermissions) -> dict[str, Any]:
        return {
            "public": self._level(data.public_level),
            "confidential": self._level(data.confidential_level),
            "private": self._level(data.private_level),
            "can_create_objects": data.can_create,
            "can_erase_objects": data.can_delete,
        }

    @staticmethod
    def _level(level: CalendarShareLevel) -> str:
        # MODIFY_IF_ORG has no API string: outside the organizer's own events it behaves as RESPOND.
        return LEVEL_TO_STR.get(level, LEVEL_TO_STR[CalendarShareLevel.RESPOND])
