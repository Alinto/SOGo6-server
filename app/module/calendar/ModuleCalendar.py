from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.module.calendar.CalendarConst import MAX_EVENT_FETCH_DAYS
from app.module.calendar.source.CalendarSources import CalendarSources
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar
from app.utils.maths.sogo_hash import generate_uuid
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.source.CalendarSource import CalendarSource


class ModuleCalendar:
    """Module for calendar and event operations."""

    def __init__(self, user: User, process_settings: ProcessSetting) -> None:
        self.user: User = user
        sogo_db_type = f"Client{process_settings.SOGO_P_DB_TYPE}"
        self._db: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=process_settings.get_db_settings(),
        )
        self._db.connect()
        self._sources: CalendarSources = CalendarSources(self._db)

    def __del__(self) -> None:
        self._db.close()

    def get_all_calendars(self) -> list[CalCalendar]:
        """Return all calendars owned by the current user."""
        return [s.calendar for s in self._sources.get_all(self.user.uid)]

    def get_calendar(self, key: str) -> CalendarSource:
        """Return the source for a calendar, or raise NOT_FOUND."""
        source = self._sources.get_by_key(self.user.uid, key)
        if source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
        return source

    def create_calendar(self, cal: CalCalendar) -> CalCalendar:
        """Persist a new calendar. Generates key, ctag and timestamps."""
        now = datetime.now(timezone.utc)
        cal.user_uid = self.user.uid
        cal.key = generate_uuid()
        cal.ctag = 0
        cal.created_at = now
        cal.updated_at = now
        source = self._sources.get(cal)
        return source.save_calendar(cal)

    def update_calendar(self, key: str, updates: dict) -> CalCalendar:
        """Apply updates to an existing calendar and persist it."""
        source = self.get_calendar(key)
        cal = source.calendar
        for field in ("name", "color", "description", "timezone", "is_default"):
            if field in updates:
                setattr(cal, field, updates[field])
        cal.updated_at = datetime.now(timezone.utc)
        source.update_calendar(cal)
        return cal

    def delete_calendar(self, key: str) -> None:
        """Delete a calendar and all its events."""
        source = self.get_calendar(key)
        source.delete_calendar()

    def get_calendar_events(
        self,
        key: str,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
    ) -> list[CalEvent]:
        """Return events for the given calendar within the [start, end] date range."""
        if start is not None and end is not None:
            if (end - start) > timedelta(days=MAX_EVENT_FETCH_DAYS):
                raise RequestException(error=err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE)
        try:
            source = self.get_calendar(key)
            events: list[CalEvent] = source.get_events(start, end, search)
            logger_calendar.debug("calendar %s returned %d events", key, len(events))
            return events
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching calendar %s: %s", key, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc
