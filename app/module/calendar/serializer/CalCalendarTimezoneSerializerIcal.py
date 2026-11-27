from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from icalendar import Calendar, Timezone

from app.module.calendar.serializer.CalCalendarSerializer import CalCalendarSerializer
from app.module.calendar.serializer.EnvelopeIcal import EnvelopeIcal
from app.utils.datetime.DateTimeUtils import resolve_tz

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar


class CalCalendarTimezoneSerializerIcal(CalCalendarSerializer[str]):
    """Serializes the time zone of a calendar to a VCALENDAR holding its VTIMEZONE alone. An unknown or malformed
    time zone is written as UTC, as resolve_tz reads it everywhere else."""

    def serialize(self, calendar: CalCalendar) -> str:  # pylint: disable=arguments-renamed
        """Return the VCALENDAR of the time zone of the calendar."""
        return CalCalendarTimezoneSerializerIcal._vcalendar(tz_name=resolve_tz(calendar.timezone).key)

    @staticmethod
    @lru_cache(maxsize=64)
    def _vcalendar(tz_name: str) -> str:
        """Build the VCALENDAR of a time zone. It is kept by name: building it takes a few milliseconds, and the
        time zone data does not change while the process runs."""
        vcalendar: Calendar = EnvelopeIcal.new_vcalendar()
        vcalendar.add_component(Timezone.from_tzid(tz_name))
        return vcalendar.to_ical().decode("utf-8")
