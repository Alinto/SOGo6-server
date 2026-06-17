from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict
from app.module.calendar.serializer.CalEventsSerializer import CalEventsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalEventsSerializerDict(CalEventsSerializer[list]):
    """Converts a list of CalEvent objects to a list of dicts."""

    def __init__(self, event_serializer: CalEventSerializerDict | None = None) -> None:
        self._event_serializer: CalEventSerializerDict = event_serializer or CalEventSerializerDict()

    def serialize(self, data: list[CalEvent]) -> list[dict[str, Any]]:
        """Convert a list of CalEvent objects to a list of plain dicts."""
        return [self._event_serializer.serialize(e) for e in data]
