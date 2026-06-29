from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.utils.serializer.Serializer import Serializer


class CalConferenceDataSerializerDict(Serializer[CalConferenceData, dict[str, Any]]):
    """Serializes a CalConferenceData (RFC 7986 CONFERENCE) to a dict.

    The nested entry points are inlined: they are a value sub-object used exclusively here.
    """

    def serialize(self, data: CalConferenceData) -> dict[str, Any]:
        """Convert a CalConferenceData to its dict representation."""
        return {
            "type": data.type,
            "url": data.url,
            "conference_id": data.conference_id,
            "entry_points": [
                {"type": ep.type, "uri": ep.uri, "label": ep.label}
                for ep in data.entry_points
            ],
        }
