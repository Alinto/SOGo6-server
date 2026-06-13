from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalConferenceData import CalConferenceData
from app.module.calendar.model.CalConferenceEntryPoint import CalConferenceEntryPoint
from app.utils.serializer.Deserializer import Deserializer


class CalConferenceDataDeserializerDict(Deserializer[dict[str, Any], CalConferenceData]):
    """Deserializes a dict into a CalConferenceData (RFC 7986 CONFERENCE).

    The nested entry points are inlined: they are a value sub-object used exclusively here.
    """

    def deserialize(self, data: dict[str, Any]) -> CalConferenceData:
        """Convert a dict into a CalConferenceData."""
        entry_points = [
            CalConferenceEntryPoint(type=ep["type"], uri=ep["uri"], label=ep.get("label"))
            for ep in data.get("entry_points", [])
        ]
        return CalConferenceData(
            type=data.get("type", ""),
            url=data.get("url"),
            conference_id=data.get("conference_id"),
            entry_points=entry_points,
        )
