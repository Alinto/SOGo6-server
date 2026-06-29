from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.utils.serializer.Deserializer import Deserializer


class CalAttendeeDeserializerDict(Deserializer[dict[str, Any], CalAttendee]):
    """Deserializes a dict into a CalAttendee (RFC 5545 ATTENDEE)."""

    def deserialize(self, data: dict[str, Any]) -> CalAttendee:
        """Convert a dict into a CalAttendee."""
        return CalAttendee(
            email=data.get("email", ""),
            name=data.get("name"),
            role=AttendeeRole(data["role"]) if "role" in data else AttendeeRole.REQUIRED,
            status=AttendeeStatus(data["status"]) if "status" in data else AttendeeStatus.NEEDS_ACTION,
            rsvp=data.get("rsvp", False),
            cutype=CalUserType(data["cutype"]) if "cutype" in data else CalUserType.INDIVIDUAL,
            delegated_from=data.get("delegated_from"),
            delegated_to=data.get("delegated_to"),
            sent_by=data.get("sent_by"),
            dir_ref=data.get("dir_ref"),
        )
