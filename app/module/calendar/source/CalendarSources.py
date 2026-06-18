from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING

from app.module.calendar.model.CalCalendar import CalCalendar
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.CalendarSourceType import CalendarSourceType
from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction, ScopeResult
from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb
from app.module.calendar.source.CalendarSourceIcsMirror import CalendarSourceIcsMirror
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.source.CalendarSource import CalendarSource


class CalendarSources:
    """Factory and lookup for CalendarSource instances.

    Single entry point for all calendar access - ModuleCalendar never touches
    RepositoryCalendar directly.
    """

    def __init__(self, db: ClientSQL) -> None:
        self._db = db
        self._repo_calendar = RepositoryCalendar(db)

    def get(self, calendar: CalCalendar) -> CalendarSource:
        """Return the appropriate CalendarSource for the given calendar.

        Both local and ICS calendars are backed by the database. ICS calendars
        are read-only mirrors - their events are populated by the sync engine,
        not by direct CRUD operations.
        """
        if calendar.source_type == CalendarSourceType.LOCAL:
            return CalendarSourceDb(self._db, calendar)

        if calendar.source_type == CalendarSourceType.ICS:
            return CalendarSourceIcsMirror(self._db, calendar)

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
        cal = self._repo_calendar.find_by_key(user_uid, key)
        return self.get(cal) if cal is not None else None

    def get_by_share_token(self, share_token: str) -> CalendarSource | None:
        """Return the source for the calendar exposed by this public subscription token.

        Not scoped to a user - the token is the capability granting access to the feed.
        """
        cal = self._repo_calendar.find_by_share_token(share_token)
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
        events.sort(key=lambda e: e.require_date_start)
        return events

    def get_freebusy_events(
        self,
        user_uid: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[CalEvent]:
        """Return events from every calendar that participates in free/busy.

        Calendars flagged include_in_freebusy=False are skipped entirely, so their events
        never contribute to the owner's busy slots.
        """
        events: list[CalEvent] = []
        for source in self.get_all(user_uid):
            if not source.calendar.include_in_freebusy:
                continue
            events.extend(source.get_events(start, end))
        events.sort(key=lambda e: e.require_date_start)
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
        tasks.sort(key=lambda e: e.require_date_start)
        return tasks

    def update_sync_config(self, calendar: CalCalendar) -> None:
        """Persist sync_config changes for an external calendar."""
        self._repo_calendar.update(calendar)

    def propagate(self, scope_result: ScopeResult, original: CalEvent | None = None) -> None:
        """Single entry point for all attendee propagation.

        Three responsibilities:
        1. Replicate the touched list (INSERT/UPDATE/DELETE) to each attendee calendar.
           - CREATE: touched contains [(new_event, INSERT)]
           - UPDATE: touched contains [(updated_master, UPDATE)] + split/occurrence entries
           - DELETE: touched contains [(deleted_event, DELETE)]
        2. Realign detached occurrences if the master's date_start moved (shift recurrence_id
           and dates on each attendee's detached rows to match the new series time).
        3. Sync the attendee list when original is provided (add copies for new attendees,
           remove copies for removed attendees).
        """
        event: CalEvent = scope_result.result
        if not event.organizer or not event.attendees:
            return

        # 1. Replicate touched events to each attendee
        for attendee in event.attendees:
            if attendee.email == event.organizer.email:
                continue
            att_source: CalendarSource | None = self._resolve_attendee_source(attendee.email)
            if att_source is None:
                continue
            for evt, action in scope_result.touched:
                try:
                    self._apply_action(att_source, evt, action)
                except Exception as exc:  # pylint: disable=broad-except
                    logger_calendar.warning(
                        "Could not propagate %s uid=%s to attendee %s: %s", action.value, evt.uid, attendee.email, exc,
                    )

            # 2. Realign detached occurrences if the master moved
            if scope_result.realign_from is not None and scope_result.realign_to is not None:
                try:
                    att_source.realign_detached_occurrences(
                        uid=event.require_uid, old_start=scope_result.realign_from, new_start=scope_result.realign_to,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    logger_calendar.warning(
                        "Could not realign detached uid=%s for attendee %s: %s", event.uid, attendee.email, exc,
                    )

        # 3. Sync attendee list (add new attendees, remove old ones)
        if original is not None:
            self._sync_attendee_list(original=original, updated=event)

    def _apply_action(self, att_source: CalendarSource, evt: CalEvent, action: EventAction) -> None:
        """Apply a single propagation action on an attendee's calendar."""
        if action == EventAction.INSERT:
            copy: CalEvent = dataclasses.replace(evt, key=None, calendar_key=att_source.calendar.key, reminders=[])
            att_source.insert_event(copy)
        elif action == EventAction.UPDATE:
            self._update_attendee_copy(att_source, evt)
        elif action == EventAction.DELETE:
            if evt.recurrence_id is not None:
                att_copy: CalEvent | None = att_source.get_event_by_recurrence_id(evt.require_uid, evt.recurrence_id)
                if att_copy is not None:
                    att_source.delete_detached_occurrence(att_copy)
            else:
                att_source.delete_event(evt.require_uid)

    def _update_attendee_copy(self, att_source: CalendarSource, event: CalEvent) -> None:
        """Find the attendee's copy and update propagatable fields."""
        if event.recurrence_id is not None:
            copy: CalEvent | None = att_source.get_event_by_recurrence_id(event.require_uid, event.recurrence_id)
        else:
            copy = att_source.get_master_event_by_uid(event.require_uid)
        if copy is None:
            return
        for field_name in CalEvent.PROPAGATABLE_FIELDS:
            setattr(copy, field_name, getattr(event, field_name))
        att_source.update_event(copy)

    def _sync_attendee_list(self, original: CalEvent | None, updated: CalEvent) -> None:
        """Synchronize attendee list of an event in local calendars.

        Handles three cases based on the difference between original and updated attendees:
        - original is None (event creation): create a copy for every attendee.
        - Attendee added (in updated but not in original): create a copy in their calendar.
        - Attendee removed (in original but not in updated): delete their copy.

        Existing attendee copies are NOT updated here - content propagation is handled
        separately by propagate().
        External attendees (no local account) are silently skipped - the iMIP agent handles them.
        """
        if not updated.organizer:
            return
        organizer_email: str = updated.organizer.email
        original_emails: set[str] = {a.email for a in (original.attendees or [])} if original else set()
        updated_emails: set[str] = {a.email for a in (updated.attendees or [])}

        added: set[str] = updated_emails - original_emails - {organizer_email}
        removed: set[str] = original_emails - updated_emails - {organizer_email}

        for email in added:
            source: CalendarSource | None = self._resolve_attendee_source(email)
            if source is None:
                continue
            try:
                copy: CalEvent = dataclasses.replace(updated, key=None, calendar_key=source.calendar.key, reminders=[])
                source.insert_event(copy)
                logger_calendar.info("Propagated event uid=%s to local attendee %s", updated.uid, email)
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Could not propagate event uid=%s to attendee %s: %s", updated.uid, email, exc)

        for email in removed:
            source = self._resolve_attendee_source(email)
            if source is None:
                continue
            try:
                source.delete_event(updated.require_uid)
                logger_calendar.info("Removed event uid=%s from local attendee %s", updated.uid, email)
            except Exception as exc:  # pylint: disable=broad-except
                logger_calendar.warning("Could not remove event uid=%s from attendee %s: %s", updated.uid, email, exc)

    def _resolve_attendee_source(self, attendee_email: str) -> CalendarSource | None:
        """Return the default writable calendar source for an attendee, or None if external."""
        source: CalendarSource | None = self.get_default(attendee_email)
        if source is None:
            writable: list[CalendarSource] = [s for s in self.get_all(attendee_email) if s.is_writable()]
            source = writable[0] if writable else None
        return source
