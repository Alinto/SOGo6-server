from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict
from app.module.calendar.serializer.CalEventsDeserializer import CalEventsDeserializer


class CalEventsDeserializerDict(CalEventsDeserializer[list]):
    """Converts a list of event dicts into CalEvent objects."""

    def __init__(self, event_deserializer: CalEventDeserializerDict | None = None) -> None:
        self._event_deserializer: CalEventDeserializerDict = event_deserializer or CalEventDeserializerDict()

    def deserialize(self, data: list[dict[str, Any]]) -> list[CalEvent]:
        """Convert a list of event dicts into CalEvent objects."""
        return [self._event_deserializer.deserialize(item) for item in data]
