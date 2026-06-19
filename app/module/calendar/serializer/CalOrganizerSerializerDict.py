from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.utils.serializer.Serializer import Serializer


class CalOrganizerSerializerDict(Serializer[CalOrganizer, dict[str, Any]]):
    """Serializes a CalOrganizer (RFC 5545 ORGANIZER) to a dict."""

    def serialize(self, data: CalOrganizer) -> dict[str, Any]:
        """Convert a CalOrganizer to its dict representation."""
        return {
            "email": data.email,
            "name": data.name,
            "role": data.role.value if data.role else None,
            "status": data.status.value if data.status else None,
            "sent_by": data.sent_by,
            "dir_ref": data.dir_ref,
        }
