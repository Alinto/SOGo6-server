from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar
from app.module.calendar.serializer.CalendarEventDeserializerIcal import CalendarEventDeserializerIcal
from app.module.calendar.serializer.CalendarEventsDeserializerIcal import CalendarEventsDeserializerIcal
from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb
from app.module.calendar.source.CalendarSourceIcs import CalendarSourceIcs
from app.utils import errors as err
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.source.CalendarSource import CalendarSource

_SOURCE_TYPE_LOCAL = "local"
_SOURCE_TYPE_ICS = "ics"


class CalendarSources:
    """Factory and lookup for CalendarSource instances.

    Single entry point for all calendar access — ModuleCalendar never touches
    RepositoryCalendar directly.
    """

    def __init__(self, db: ClientSQL) -> None:
        self._db = db
        self._repo_calendar = RepositoryCalendar(db)

    def get(self, calendar: CalCalendar) -> CalendarSource:
        """Return the appropriate CalendarSource for the given calendar."""
        if calendar.source_type == _SOURCE_TYPE_LOCAL:
            return CalendarSourceDb(self._db, calendar)

        if calendar.source_type == _SOURCE_TYPE_ICS:
            url = (calendar.sync_config or {}).get("url")
            if not url:
                logger_calendar.error("ICS calendar key=%s has no sync_config.url", calendar.key)
                raise BugException(f"ICS calendar key={calendar.key} missing sync_config.url")
            deserializer = CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal())
            return CalendarSourceIcs(calendar, url, deserializer)

        logger_calendar.error("Unknown source_type=%s for calendar key=%s", calendar.source_type, calendar.key)
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def get_all(self, user_uid: str) -> list[CalendarSource]:
        """Return a source for every calendar owned by user_uid."""
        return [self.get(cal) for cal in self._repo_calendar.find_all(user_uid)]

    def get_by_key(self, user_uid: str, key: str) -> CalendarSource | None:
        """Return the source for a specific calendar, or None if not found."""
        cal = self._repo_calendar.find_by_key(user_uid, key)
        return self.get(cal) if cal is not None else None
