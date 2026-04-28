from __future__ import annotations

import dataclasses
import os
from datetime import datetime

# pylint: disable=fixme
from typing import TYPE_CHECKING

from app.module.calendar.model.CalCalendar import CalCalendar
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
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.source.CalendarSource import CalendarSource

_SOURCE_TYPE_LOCAL = "local"
_SOURCE_TYPE_ICS = "ics"
_ICS_STUB_KEY = "ics"  # TODO: TO DELETE


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

    def get_default(self, user_uid: str) -> CalendarSource | None:
        """Return the default writable calendar source for user_uid, or None if the user has no local calendar."""
        cal: CalCalendar | None = self._repo_calendar.get_default_calendar_for_user(user_uid)
        return self.get(cal) if cal is not None else None

    def find_by_uid(self, user_uid: str, uid: str) -> tuple[CalendarSource, CalEvent] | None:
        """Find a master event by RFC 5545 UID across all calendars of user_uid.

        Returns (source, event) for the first calendar containing a master row with that UID,
        or None if no such event exists.
        """
        for source in self.get_all(user_uid):
            event: CalEvent | None = source.get_master_event_by_uid(uid)
            if event is not None:
                return source, event
        return None

    def get_by_key(self, user_uid: str, key: str) -> CalendarSource | None:
        """Return the source for a specific calendar, or None if not found."""
        # TODO: TO DELETE — ICS stub: calendar_key "ics" resolves to ICS_STUB_URL env var
        if key == _ICS_STUB_KEY:
            url = os.getenv("ICS_STUB_URL") or "https://calendar.google.com/calendar/ical/8f0aaf825b126f8f3f8ae5799c3c8699bcf04b115bfee085467e19f71ba084ba%40group.calendar.google.com/private-5e54ad70f6be3e5a740648483b0469dd/basic.ics"
            if not url:
                return None
            stub_cal = CalCalendar(user_uid=user_uid, name="ICS Stub", key=_ICS_STUB_KEY, source_type=_SOURCE_TYPE_ICS)
            return CalendarSourceIcs(stub_cal, url, CalendarEventsDeserializerIcal(CalendarEventDeserializerIcal()))
        cal = self._repo_calendar.find_by_key(user_uid, key)
        return self.get(cal) if cal is not None else None

    def get_events(
        self,
        user_uid: str,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
        calendar_key: str | None = None,
    ) -> list[CalEvent]:
        """Return events for user_uid, optionally restricted to a single calendar.

        When calendar_key is None, events from all user calendars are merged and sorted.
        Raises ERROR_CALENDAR_NOT_FOUND if calendar_key is given but does not exist.
        """
        if calendar_key is not None:
            source = self.get_by_key(user_uid, calendar_key)
            if source is None:
                raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
            return source.get_events(start, end, search)
        events: list[CalEvent] = []
        for source in self.get_all(user_uid):
            events.extend(source.get_events(start, end, search))
        events.sort(key=lambda e: e.date_start)
        return events

    def get_tasks(
        self,
        user_uid: str,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
        calendar_key: str | None = None,
    ) -> list[CalEvent]:
        """Return tasks for user_uid, optionally restricted to a single calendar.

        When calendar_key is None, tasks from all user calendars are merged and sorted.
        Raises ERROR_CALENDAR_NOT_FOUND if calendar_key is given but does not exist.
        """
        if calendar_key is not None:
            source = self.get_by_key(user_uid, calendar_key)
            if source is None:
                raise RequestException(error=err.ERROR_CALENDAR_NOT_FOUND)
            return source.get_tasks(start, end, search)
        tasks: list[CalEvent] = []
        for source in self.get_all(user_uid):
            tasks.extend(source.get_tasks(start, end, search))
        tasks.sort(key=lambda e: e.date_start)
        return tasks

    def propagate_new_event_to_local_attendees(self, event: CalEvent) -> None:
        """Insert a copy of a newly created event into each local attendee's calendar.

        Called once at creation time — this is NOT for updates (use CalendarSourceDb.update_event
        with propagate=True for that). The goal is to make the invitation visible in the attendee's
        calendar immediately, without waiting for an iMIP email exchange.

        For each attendee listed on the event:
        - Skip the organizer (they already have the master copy).
        - Resolve the attendee's default writable calendar; fall back to their first writable calendar
          if no default is set. Skip entirely if no writable calendar is found (external user).
        - Insert a stripped copy: key is reset (DB assigns a new one), reminders are cleared
          (each attendee manages their own), calendar_key points to the attendee's calendar.

        External attendees (no local account → no calendars) are silently skipped; the iMIP
        agent handles them via email.
        """
        if not event.organizer or not event.attendees:
            return
        for attendee in event.attendees:
            # Organizer already holds the master row — do not create a duplicate
            if attendee.email == event.organizer.email:
                continue
            attendee_source: CalendarSource | None = self.get_default(attendee.email)
            if attendee_source is None:
                # No default calendar set — fall back to first writable calendar
                writable: list[CalendarSource] = [s for s in self.get_all(attendee.email) if s.is_writable()]
                attendee_source = writable[0] if writable else None
            if attendee_source is None:
                # No local calendar at all — external attendee, iMIP handles it
                continue
            try:
                copy: CalEvent = dataclasses.replace(event, key=None, calendar_key=attendee_source.calendar.key, reminders=[])
                attendee_source.insert_event(copy)
                logger_calendar.info("Propagated event uid=%s to local attendee %s", event.uid, attendee.email)
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Could not propagate event uid=%s to attendee %s: %s", event.uid, attendee.email, exc)
