from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalendarEventDeserializerDict import CalendarEventDeserializerDict
from app.module.calendar.serializer.CalendarEventsDeserializer import CalendarEventsDeserializer


class CalendarEventsDeserializerDict(CalendarEventsDeserializer[list]):
    """Converts a list of event dicts into CalEvent objects."""

    def __init__(self, event_deserializer: CalendarEventDeserializerDict | None = None) -> None:
        self._event_deserializer: CalendarEventDeserializerDict = event_deserializer or CalendarEventDeserializerDict()

    def deserialize(self, data: list[dict[str, Any]]) -> list[CalEvent]:
        """Convert a list of event dicts into CalEvent objects."""
        return [self._event_deserializer.deserialize(item) for item in data]
