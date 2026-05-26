from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from icalendar import Calendar

from app.module.calendar.serializer.CalendarSerializer import CalendarSerializer
from app.module.calendar.serializer.IcalConst import CALSCALE, PRODID
from app.module.calendar.serializer.IcalSerializerUtils import new_vcalendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.serializer.CalendarEventsSerializerIcal import CalendarEventsSerializerIcal


class CalendarSerializerIcal(CalendarSerializer[str]):
    """Serializes a calendar collection to a full VCALENDAR string (RFC 5545).

    Owns the calendar-level header (PRODID/VERSION/CALSCALE plus the X-WR-* descriptors read by
    Apple/Google/Outlook) and delegates the body — one component per event — to an injected
    CalendarEventsSerializerIcal. When a refresh interval is provided, the output advertises a
    suggested resync period (REFRESH-INTERVAL per RFC 7986 §5.7, and X-PUBLISHED-TTL for clients
    that only read the legacy property) — used for live subscription feeds, not one-off exports.
    """

    def __init__(
        self, events_serializer: CalendarEventsSerializerIcal, refresh_interval: timedelta | None = None,
    ) -> None:
        self._events_serializer: CalendarEventsSerializerIcal = events_serializer
        self._refresh_interval: timedelta | None = refresh_interval

    def serialize(self, calendar: CalCalendar) -> str:  # pylint: disable=arguments-renamed
        """Wrap the calendar's events in a VCALENDAR with its calendar-level header."""
        cal: Calendar = new_vcalendar(
            prodid=calendar.prodid or PRODID,
            calscale=calendar.calscale or CALSCALE,
            method=calendar.method,
        )
        cal.add("x-wr-calname", calendar.name)
        if calendar.description:
            cal.add("x-wr-caldesc", calendar.description)
        cal.add("x-wr-timezone", calendar.timezone)
        for prop_name, prop_value in calendar.extra_properties.items():
            cal.add(prop_name, prop_value)

        if self._refresh_interval is not None:
            cal.add("refresh-interval", self._refresh_interval, parameters={"VALUE": "DURATION"})
            cal.add("x-published-ttl", self._refresh_interval, parameters={"VALUE": "DURATION"})

        for component in self._events_serializer.serialize(calendar.events):
            cal.add_component(component)

        return cal.to_ical().decode("utf-8")
