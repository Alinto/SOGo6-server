from __future__ import annotations

from typing import TYPE_CHECKING

from icalendar import Component

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalendarEventsSerializer import CalendarEventsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalendarEventSerializerIcal import CalendarEventSerializerIcal


class CalendarEventsSerializerIcal(CalendarEventsSerializer[list]):
    """Serializes a list of CalEvent objects into iCalendar components (VEVENT / VTODO).

    Produces the body components only; wrapping them in a VCALENDAR (with the calendar-level
    header) is the responsibility of CalendarSerializerIcal. Delegates per-component building
    to an injected CalendarEventSerializerIcal instance.
    """

    def __init__(self, event_serializer: CalendarEventSerializerIcal) -> None:
        self._event_serializer: CalendarEventSerializerIcal = event_serializer

    def serialize(self, events: list[CalEvent]) -> list[Component]:  # pylint: disable=arguments-renamed
        """Build one VEVENT or VTODO component per event, dispatching on component_type."""
        components: list[Component] = []
        for event in events:
            if event.component_type == ComponentType.TASK:
                components.append(self._event_serializer.to_vtodo(event))
            else:
                components.append(self._event_serializer.to_vevent(event))
        return components
