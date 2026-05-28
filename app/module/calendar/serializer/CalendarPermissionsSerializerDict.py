from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalendarPermissions import CalendarPermissions
from app.module.calendar.serializer.Serializer import Serializer


class CalendarPermissionsSerializerDict(Serializer[CalendarPermissions, dict[str, Any]]):
    """Serializes CalendarPermissions to a dict for API responses."""

    def serialize(self, data: CalendarPermissions) -> dict[str, Any]:
        return {
            "public_level": data.public_level.name.lower(),
            "confidential_level": data.confidential_level.name.lower(),
            "private_level": data.private_level.name.lower(),
            "can_create": data.can_create,
            "can_delete": data.can_delete,
        }
