from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import os  # TODO: No need when stub will be removed  # pylint: disable=fixme

from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.module.calendar.source.CalendarSource import CalendarSource
from app.module.calendar.source.CalendarSourceIcs import CalendarSourceIcs
from app.utils.errors import ERROR_UNKOWN
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.auth.User import User
    from app.module.calendar.model.CalEvent import CalEvent


class ModuleCalendar:
    """
    Module to handle calendar operations (events, reminders, attendees, recurrence).
    """

    def __init__(self, user: User) -> None:
        self.user: User = user

    def get_calendar_events(
        self,
        calendar_id: str,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
    ) -> list[CalEvent]:
        """Return events for the given calendar within the [start, end] date range.

        None values for start/end are forwarded to CalendarSource, which applies
        its own defaults (1970-01-01 UTC and now UTC respectively).

        :param calendar_id: The calendar identifier (hash).
        :param start: Lower bound (UTC, inclusive). None means no lower bound.
        :param end: Upper bound (UTC, inclusive). None means up to now.
        :param search: Optional full-text filter on title, description and location.
        :return: Filtered list of CalEvent objects.
        """
        try:
            source: CalendarSource = self._resolve_source(calendar_id)
            events: list[CalEvent] = source.get_events(start, end, search)
            logger_calendar.debug("calendar %s returned %d events", calendar_id, len(events))
            return events
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching calendar %s: %s", calendar_id, exc)
            raise RequestException(error=ERROR_UNKOWN) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_source(self, calendar_id: str) -> CalendarSource:
        """Build the CalendarSource for the given calendar identifier."""
        deserializer: CalendarEventsDeserializerIcal = CalendarEventsDeserializerIcal(
            CalendarEventDeserializerIcal()
        )
        # TODO: Remove stub once calendar implemented  # pylint: disable=fixme
        return CalendarSourceIcs(
            ics_url=os.getenv("ICS_STUB_URL") or "https://calendar.google.com/calendar/ical/8f0aaf825b126f8f3f8ae5799c3c8699bcf04b115bfee085467e19f71ba084ba%40group.calendar.google.com/private-5e54ad70f6be3e5a740648483b0469dd/basic.ics",
            deserializer=deserializer,
        )
