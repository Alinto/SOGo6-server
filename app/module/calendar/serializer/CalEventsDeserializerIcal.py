from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.module.calendar.serializer.CalEventsDeserializer import CalEventsDeserializer
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalEventDeserializerIcal import CalEventDeserializerIcal


class CalEventsDeserializerIcal(CalEventsDeserializer[str]):
    """
    Deserializes a full VCALENDAR (ICS text) into a list of CalEvent objects.

    Delegates VEVENT parsing to an injected CalEventDeserializerIcal instance,
    keeping calendar-level and event-level concerns separate.
    """

    def __init__(self, event_deserializer: CalEventDeserializerIcal) -> None:
        self._event_deserializer: CalEventDeserializerIcal = event_deserializer

    def deserialize(self, text: str) -> list[CalEvent]:  # pylint: disable=arguments-renamed
        """Parse ICS text and return all VEVENT and VTODO components as CalEvent objects.

        Raises RequestException if the ICS structure is unparseable.
        Individual malformed components are skipped with a warning.
        """
        events: list[CalEvent] = []
        component: Any
        for component in self._event_deserializer.iter_vevents(text):
            try:
                events.append(self._event_deserializer.deserialize_vevent(component))
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Skipping malformed VEVENT: %s", exc)
        for component in self._event_deserializer.iter_vtodos(text):
            try:
                events.append(self._event_deserializer.deserialize_vtodo(component))
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Skipping malformed VTODO: %s", exc)
        return events
