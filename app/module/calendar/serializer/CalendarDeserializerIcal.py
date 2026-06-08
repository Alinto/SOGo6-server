from __future__ import annotations

from typing import TYPE_CHECKING, cast

from icalendar import Calendar

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.serializer.CalendarDeserializer import CalendarDeserializer
from app.utils.errors import ERROR_CALENDAR_ICS_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal

# Calendar-level properties mapped onto dedicated CalCalendar fields; everything else (other
# X-* descriptors) is preserved in extra_properties so a round-trip does not lose information.
_MAPPED_PROPS: frozenset[str] = frozenset({
    "PRODID", "VERSION", "CALSCALE", "METHOD",
    "X-WR-CALNAME", "X-WR-CALDESC", "X-WR-TIMEZONE",
    "REFRESH-INTERVAL", "X-PUBLISHED-TTL",
})


class CalendarDeserializerIcal(CalendarDeserializer[str]):
    """Deserializes a full VCALENDAR (ICS text) into a CalCalendar with its events populated.

    Reads the calendar-level header (X-WR-CALNAME/CALDESC/TIMEZONE, PRODID, CALSCALE, METHOD,
    and any remaining X-* into extra_properties) and delegates the body to an injected
    CalendarEventsDeserializerIcal, which fills ``calendar.events``.
    """

    def __init__(self, events_deserializer: CalendarEventsDeserializerIcal) -> None:
        self._events_deserializer: CalendarEventsDeserializerIcal = events_deserializer

    def deserialize(self, text: str) -> CalCalendar:  # pylint: disable=arguments-renamed
        """Parse ICS text into a CalCalendar (header + events). Raises on unparseable input."""
        try:
            cal: Calendar = cast(Calendar, Calendar.from_ical(text))
        except Exception as exc:
            logger_calendar.error("Failed to parse VCALENDAR header: %s", exc)
            raise RequestException(error=ERROR_CALENDAR_ICS_PARSE_FAILED) from exc

        calendar: CalCalendar = CalCalendar(
            user_uid="",
            name=self._text(cal, "x-wr-calname"),
            description=self._optional_text(cal, "x-wr-caldesc"),
            timezone=self._text(cal, "x-wr-timezone") or "UTC",
            prodid=self._optional_text(cal, "prodid"),
            calscale=self._optional_text(cal, "calscale"),
            method=self._optional_text(cal, "method"),
        )
        calendar.extra_properties = {
            key: str(cal.get(key)) for key in cal.keys() if key.upper() not in _MAPPED_PROPS
        }
        calendar.events = self._events_deserializer.deserialize(text)
        return calendar

    @staticmethod
    def _text(cal: Calendar, key: str) -> str:
        value = cal.get(key)
        return str(value) if value is not None else ""

    @staticmethod
    def _optional_text(cal: Calendar, key: str) -> str | None:
        value = cal.get(key)
        return str(value) if value is not None else None
