from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalendarEventsSerializer import CalendarEventsSerializer
from app.module.calendar.serializer.CalendarEventSerializerJson import CalendarEventSerializerJson

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventsSerializerJson(CalendarEventsSerializer):
    """
    Serializes a list of CalEvent objects to a JSON array.
    Datetimes are formatted as ISO 8601 UTC with millisecond precision.
    """

    def __init__(self, event_serializer: CalendarEventSerializerJson | None = None) -> None:
        self._event_serializer: CalendarEventSerializerJson = event_serializer or CalendarEventSerializerJson()

    def serialize(self, events: list[CalEvent]) -> str:
        """Serialize a list of CalEvent objects to a JSON array string."""
        return json.dumps(self.to_list(events), ensure_ascii=False)

    def to_list(self, events: list[CalEvent]) -> list[dict[str, Any]]:
        """Convert a list of CalEvent objects to a list of plain dicts."""
        return [self._event_serializer.to_dict(e) for e in events]

    def to_response(self, events: list[CalEvent]) -> dict[str, Any]:
        """Return the API data payload: events list and total_count."""
        event_list = self.to_list(events)
        return {"events": event_list, "total_count": len(event_list)}
