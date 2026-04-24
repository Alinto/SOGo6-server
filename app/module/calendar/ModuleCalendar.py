from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

# pylint: disable=fixme

from app.module.calendar.CalendarConst import MAX_EVENT_FETCH_DAYS, MAX_FREEBUSY_DAYS, MAX_TASK_FETCH_DAYS
from app.module.calendar.freebusy.FreeBusyEngine import FreeBusyEngine, FreeBusyPrefs
from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent
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

    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
    from app.module.calendar.source.CalendarSource import CalendarSource
    from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb


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

    def create_personal_calendar(self, user_uid: str, name: str = "Personal Calendar") -> CalCalendar:
        """Create and persist the default personal calendar for a user.

        If the user already has a default calendar, returns it without creating a new one.
        """
        for source in self._sources.get_all(user_uid):
            if source.calendar.is_default:
                return source.calendar
        cal = CalCalendar(user_uid=user_uid, name=name, is_default=True)
        cal.key = generate_uuid()
        cal.ctag = 0
        source = self._sources.get(cal)
        return source.save_calendar(cal)

    # ------------------------------------------------------------------
    # Calendars
    # ------------------------------------------------------------------
    def get_all_calendars(self) -> list[CalCalendar]:
        """Return all calendars owned by the current user."""
        return [s.calendar for s in self._sources.get_all(self.user.uid)]

    def get_calendar(self, key: str) -> CalendarSource:
        """Return the source for a calendar, or raise NOT_FOUND."""
        source:CalendarSource = self._sources.get_by_key(self.user.uid, key)
        if source is None:
            raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
        return source

    def create_calendar(self, cal: CalCalendar) -> CalCalendar:
        """Persist a new calendar. Generates key and ctag."""
        cal.user_uid = self.user.uid
        cal.key = generate_uuid()
        cal.ctag = 0
        source:CalendarSource = self._sources.get(cal)
        return source.save_calendar(cal)

    def update_calendar(self, key: str, updates: dict) -> CalCalendar:
        """Apply updates to an existing calendar and persist it."""
        source:CalendarSource = self.get_calendar(key)
        cal = source.calendar
        cal.apply_update(updates)
        source.update_calendar(cal)
        return cal

    def delete_calendar(self, key: str) -> None:
        """Delete a calendar and all its events."""
        source:CalendarSource = self.get_calendar(key)
        source.delete_calendar()

    def _bump_ctag(self, source: CalendarSource) -> None:
        """Increment the calendar's ctag to signal that its event collection has changed.

        CalDAV clients use the CS:getctag extension (RFC 4791 / draft-daboo-caldav-extensions)
        to detect changes without fetching every event: they cache the ctag and re-query only
        when the value differs from the server's current value.
        """
        cal = source.calendar
        cal.ctag = (cal.ctag or 0) + 1
        source.update_calendar(cal)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _find_source_for_event(self, event_key: str) -> tuple[CalendarSource, CalEvent]:
        """Find the source and event for a given event key across user's calendars."""
        for source in self._sources.get_all(self.user.uid):
            event = source.get_event(event_key)
            if event is not None:
                return source, event
        raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)

    def create_event(self, calendar_key: str, event: CalEvent) -> CalEvent:
        """Persist a new event in the calendar and return it."""
        source:CalendarSource = self.get_calendar(calendar_key)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        event.calendar_key = source.calendar.key
        if not event.uid:
            event.uid = generate_uuid()
        try:
            created = source.insert_event(event)
            self._bump_ctag(source)
            # TODO: send iMIP email (METHOD:REQUEST) to attendees
            return created
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error creating event in calendar %s: %s", calendar_key, exc)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED) from exc

    def get_event(self, event_key: str) -> CalEvent:
        """Return a single event by key across the user's calendars, or raise NOT_FOUND."""
        _, event = self._find_source_for_event(event_key)
        return event

    def update_event(self, event_key: str, updates: dict) -> CalEvent:
        """Apply partial updates to an event and persist it."""
        source, event = self._find_source_for_event(event_key)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        event.apply_update(updates)
        try:
            source.update_event(event)
            self._bump_ctag(source)
            # TODO: send iMIP email (METHOD:REQUEST) to attendees if organizer field is set
            return event
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error updating event %s: %s", event_key, exc)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def delete_event(self, event_key: str) -> None:
        """Soft-delete an event by key.

        If the event is a detached occurrence (recurrence_id is set), only that row is deleted
        and its recurrence_id is added to the master's EXDATE so the slot stays cancelled.
        Otherwise the master and all its detached occurrences are deleted.
        """
        source, event = self._find_source_for_event(event_key)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        try:
            if event.recurrence_id is not None:
                source.delete_detached_occurrence(event)
            else:
                source.delete_event(event.uid)
            self._bump_ctag(source)
            # TODO: send iMIP email (METHOD:CANCEL) to attendees if organizer field is set
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error deleting event %s: %s", event_key, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_events(
        self,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
        key: str | None = None,
    ) -> list[CalEvent]:
        """Return events within [start, end], optionally restricted to a single calendar.

        When key is None, events from all user calendars are merged.
        The date-range limit is bypassed when a search query is present.
        """
        if search is None and start is not None and end is not None:
            if (end - start) > timedelta(days=MAX_EVENT_FETCH_DAYS):
                raise RequestException(error=err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE)
        try:
            events: list[CalEvent] = self._sources.get_events(self.user.uid, start, end, search, key)
            logger_calendar.debug("returned %d events (calendar=%s)", len(events), key or "all")
            return events
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching events (calendar=%s): %s", key, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------
    def create_task(self, calendar_key: str, task: CalEvent) -> CalEvent:
        """Persist a new VTODO in the calendar and return it."""
        task.component_type = ComponentType.TASK
        source: CalendarSource = self.get_calendar(calendar_key)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        task.calendar_key = source.calendar.key
        if not task.uid:
            task.uid = generate_uuid()
        try:
            created = source.insert_event(task)
            self._bump_ctag(source)
            return created
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error creating task in calendar %s: %s", calendar_key, exc)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_INSERT_FAILED) from exc

    def get_task(self, task_key: str) -> CalEvent:
        """Return a single VTODO by key, or raise TASK_NOT_FOUND."""
        _, task = self._find_source_for_event(task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        return task

    def update_task(self, task_key: str, updates: dict) -> CalEvent:
        """Apply partial updates to a VTODO and persist it."""
        source, task = self._find_source_for_event(task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        task.apply_update(updates)
        try:
            source.update_event(task)
            self._bump_ctag(source)
            return task
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error updating task %s: %s", task_key, exc)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def delete_task(self, task_key: str) -> None:
        """Soft-delete a VTODO by key."""
        source, task = self._find_source_for_event(task_key)
        if task.component_type != ComponentType.TASK:
            raise RequestException(error=err.ERROR_CALENDAR_TASK_NOT_FOUND)
        if not source.is_writable():
            raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
        try:
            source.delete_event(task.uid)
            self._bump_ctag(source)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error deleting task %s: %s", task_key, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    def get_tasks(
        self,
        start: datetime | None,
        end: datetime | None,
        search: str | None,
        key: str | None = None,
    ) -> list[CalEvent]:
        """Return VTODO tasks within [start, end], optionally restricted to a single calendar.

        When key is None, tasks from all user calendars are merged.
        The date-range limit is bypassed when a search query is present.
        """
        if search is None and start is not None and end is not None:
            if (end - start) > timedelta(days=MAX_TASK_FETCH_DAYS):
                raise RequestException(error=err.ERROR_CALENDAR_DATE_RANGE_TOO_LARGE)
        try:
            tasks: list[CalEvent] = self._sources.get_tasks(self.user.uid, start, end, search, key)
            logger_calendar.debug("returned %d tasks (calendar=%s)", len(tasks), key or "all")
            return tasks
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error fetching tasks (calendar=%s): %s", key, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    # TODO: Implement in admin API
    def clean(self, user_uid: str | None = None, calendar_key: str | None = None) -> int:
        """Physically remove soft-deleted event rows for a calendar or all calendars of a user.

        Returns the total number of rows purged. At least one of user_uid or calendar_key must
        be provided. When user_uid is given, all calendars currently owned by that user are cleaned.
        """
        repo = RepositoryEvent(self._db)
        if calendar_key is not None:
            return repo.purge_deleted(calendar_key)
        if user_uid is not None:
            keys = [s.calendar.key for s in self._sources.get_all(user_uid)]
            return sum(repo.purge_deleted(k) for k in keys)
        return 0

    # ------------------------------------------------------------------
    # FreeBusy
    # ------------------------------------------------------------------
    def get_freebusy(
        self,
        target_uid: str,
        start: datetime,
        end: datetime,
        prefs: FreeBusyPrefs,
    ) -> list[CalFreeBusyPeriod]:
        """Return merged free/busy periods for target_uid in [start, end].

        prefs must be provided by the caller (loaded from user settings).

        IMPORTANT — timezone: the off-hours computation (when prefs.busy_off_hours is True)
        uses prefs.timezone, which must be the target user's IANA timezone (SOGO_U_TIMEZONE).
        This means that "working hours" (e.g. 09:00–17:00) are interpreted in that timezone,
        not in UTC or in the requester's timezone. The caller (interface layer) is responsible
        for loading SOGO_U_TIMEZONE and setting it on FreeBusyPrefs before calling this method.
        """
        if (end - start) > timedelta(days=MAX_FREEBUSY_DAYS):
            raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_DATE_RANGE_TOO_LARGE)
        try:
            events: list[CalEvent] = self._sources.get_events(target_uid, start, end)
            return FreeBusyEngine().compute(events, start, end, prefs)
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.error("Unexpected error computing freebusy for uid=%s: %s", target_uid, exc)
            raise RequestException(error=err.ERROR_UNKOWN) from exc
