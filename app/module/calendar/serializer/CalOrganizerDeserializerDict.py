from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.utils.logger.logger import logger_calendar
from app.utils.serializer.Deserializer import Deserializer


class CalOrganizerDeserializerDict(Deserializer[dict[str, Any], CalOrganizer]):
    """Deserializes a dict into a CalOrganizer (RFC 5545 ORGANIZER)."""

    def deserialize(self, data: dict[str, Any]) -> CalOrganizer:
        """Convert a dict into a CalOrganizer."""
        return CalOrganizer(
            email=data.get("email", ""),
            name=data.get("name"),
            role=self._parse_enum(AttendeeRole, data.get("role")),
            status=self._parse_enum(AttendeeStatus, data.get("status")),
            sent_by=data.get("sent_by"),
            dir_ref=data.get("dir_ref"),
        )

    @staticmethod
    def _parse_enum(enum_cls: type, value: str | None) -> Any:
        """Parse an enum from its string value; return None on missing or unknown value."""
        if value is None:
            return None
        try:
            return enum_cls(value)
        except ValueError:
            logger_calendar.warning("Unknown %s value %r, using None", enum_cls.__name__, value)
            return None
