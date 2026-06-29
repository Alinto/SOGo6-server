from __future__ import annotations

from typing import TYPE_CHECKING

from icalendar import Component

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalEventsSerializer import CalEventsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.serializer.CalEventSerializerIcal import CalEventSerializerIcal


class CalEventsSerializerIcal(CalEventsSerializer[list]):
    """Serializes a list of CalEvent objects into iCalendar components (VEVENT / VTODO).

    Produces the body components only; wrapping them in a VCALENDAR (with the calendar-level
    header) is the responsibility of CalCalendarSerializerIcal. Delegates per-component building
    to an injected CalEventSerializerIcal instance.
    """

    def __init__(self, event_serializer: CalEventSerializerIcal) -> None:
        self._event_serializer: CalEventSerializerIcal = event_serializer

    def serialize(self, events: list[CalEvent]) -> list[Component]:  # pylint: disable=arguments-renamed
        """Build one VEVENT or VTODO component per event, dispatching on component_type."""
        components: list[Component] = []
        for event in events:
            if event.component_type == ComponentType.TASK:
                components.append(self._event_serializer.to_vtodo(event))
            else:
                components.append(self._event_serializer.to_vevent(event))
        return components
