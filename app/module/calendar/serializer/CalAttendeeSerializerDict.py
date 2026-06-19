from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalAttendee import CalAttendee
from app.utils.serializer.Serializer import Serializer


class CalAttendeeSerializerDict(Serializer[CalAttendee, dict[str, Any]]):
    """Serializes a CalAttendee (RFC 5545 ATTENDEE) to a dict."""

    def serialize(self, data: CalAttendee) -> dict[str, Any]:
        """Convert a CalAttendee to its dict representation."""
        return {
            "email": data.email,
            "name": data.name,
            "role": data.role.value,
            "status": data.status.value,
            "rsvp": data.rsvp,
            "cutype": data.cutype.value,
            "delegated_from": data.delegated_from,
            "delegated_to": data.delegated_to,
            "sent_by": data.sent_by,
            "dir_ref": data.dir_ref,
        }
