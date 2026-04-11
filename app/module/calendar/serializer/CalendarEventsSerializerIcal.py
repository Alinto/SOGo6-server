from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.calendar.serializer.CalendarEventsSerializer import CalendarEventsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal


class CalendarEventsSerializerIcal(CalendarEventsSerializer):
    """
    Serializes a list of CalEvent objects into a RFC 5545-compliant ICS string.

    Wraps events in a VCALENDAR with default SOGo6 properties.
    Delegates VEVENT building to an injected CalendarEventSerializerIcal instance.
    """

    def __init__(self, event_serializer: CalendarEventSerializerIcal) -> None:
        self._event_serializer: CalendarEventSerializerIcal = event_serializer

    def serialize(self, events: list[CalEvent]) -> str:
        """Serialize a list of CalEvent objects to a VCALENDAR ICS string."""
        return self._event_serializer.build_vcalendar(events)
