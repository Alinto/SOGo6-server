from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalendarEventSerializerDict import CalendarEventSerializerDict
from app.module.calendar.serializer.CalendarEventsSerializer import CalendarEventsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventsSerializerDict(CalendarEventsSerializer[list]):
    """Converts a list of CalEvent objects to a list of dicts."""

    def __init__(self, event_serializer: CalendarEventSerializerDict | None = None) -> None:
        self._event_serializer: CalendarEventSerializerDict = event_serializer or CalendarEventSerializerDict()

    def serialize(self, data: list[CalEvent]) -> list[dict[str, Any]]:
        """Convert a list of CalEvent objects to a list of plain dicts."""
        return [self._event_serializer.serialize(e) for e in data]
