from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalendarEventsDeserializer import CalendarEventsDeserializer
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal


class CalendarEventsDeserializerIcal(CalendarEventsDeserializer):
    """
    Deserializes a full VCALENDAR (ICS text) into a list of CalEvent objects.

    Delegates VEVENT parsing to an injected CalendarEventDeserializerIcal instance,
    keeping calendar-level and event-level concerns separate.
    """

    def __init__(self, event_deserializer: CalendarEventDeserializerIcal) -> None:
        self._event_deserializer: CalendarEventDeserializerIcal = event_deserializer

    def deserialize(self, text: str) -> list[CalEvent]:
        """Parse ICS text and return all VEVENT components as CalEvent objects.

        Raises RequestException if the ICS structure is unparseable.
        Individual malformed VEVENTs are skipped with a warning.
        """
        events: list[CalEvent] = []
        component: Any
        for component in self._event_deserializer.iter_vevents(text):
            try:
                events.append(self._event_deserializer.deserialize_vevent(component))
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Skipping malformed VEVENT: %s", exc)
        return events
