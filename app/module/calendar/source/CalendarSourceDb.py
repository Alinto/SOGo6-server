from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent
from app.module.calendar.repository.RepositoryReminder import RepositoryReminder
from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction
from app.module.calendar.rrule.RruleEngine import RruleEngine
from app.module.calendar.source.CalendarSource import CalendarSource
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus


class CalendarSourceDb(CalendarSource):
    """Calendar source backed by the local database (sogo_calendars + sogo_events)."""

    def __init__(self, db: ClientSQL, calendar: CalCalendar) -> None:
        super().__init__(calendar)
        self._repo_calendar = RepositoryCalendar(db)
        self._repo_event = RepositoryEvent(db)
        self._repo_reminder = RepositoryReminder(db)

    def is_writable(self) -> bool:
        return True

    def save_calendar(self, calendar: CalCalendar) -> CalCalendar:
        """Insert a new calendar row and return it with id and key populated.

        If is_default=True, all other calendars of the same user are cleared.
        """
        self._calendar = self._repo_calendar.insert(calendar)
        if self._calendar.is_default:
            self._repo_calendar.clear_default(self._calendar.user_uid, self._calendar.id)
        return self._calendar

    def update_calendar(self, calendar: CalCalendar) -> None:
        """Persist changes to an existing calendar row.

        If is_default=True, all other calendars of the same user are cleared.
        """
        if calendar.is_default:
            self._repo_calendar.clear_default(calendar.user_uid, calendar.id)
        self._repo_calendar.update(calendar)
        self._calendar = calendar

    def delete_calendar(self) -> None:
        """Soft-delete all events and their reminders, then hard-delete the calendar row."""
        event_keys: list[str] = self._repo_event.find_keys(self._calendar.key)
        for key in event_keys:
            self._repo_reminder.delete(key)
        self._repo_event.delete_all(self._calendar.key)
        self._repo_calendar.delete(self._calendar.id)

    def _fetch_events(self, start: datetime, end: datetime, search: str | None = None) -> list[CalEvent]:
        """Query non-deleted VEVENT components overlapping [start, end]."""
        return self._repo_event.find_by_calendar(self._calendar.key, start, end, search)

    def _fetch_tasks(self, start: datetime, end: datetime, search: str | None = None) -> list[CalEvent]:
        """Query non-deleted VTODO components overlapping [start, end]."""
        return self._repo_event.find_by_calendar(
            self._calendar.key, start, end, search, component_type=ComponentType.TASK
        )

    def get_sync_metadata(self) -> list:
        """Return lightweight CalEventSyncMeta for all non-deleted events (for sync diff)."""
        return self._repo_event.find_sync_metadata(self._calendar.key)

    def get_event(self, event_key: str) -> CalEvent | None:
        """Return a single event by its opaque key, or None if not found."""
        event = self._repo_event.find_by_key(self._calendar.key, event_key)
        if event is not None and self._calendar.timezone:
            event.calendar_timezone = self._calendar.timezone
        return event

    def get_master_event_by_uid(self, uid: str) -> CalEvent | None:
        """Return the master event (recurrence_id IS NULL) matching the given UID within this calendar, or None."""
        event: CalEvent | None = self._repo_event.find_master_by_uid(self._calendar.key, uid)
        if event is not None and self._calendar.timezone:
            event.calendar_timezone = self._calendar.timezone
        return event

    def get_event_by_recurrence_id(self, uid: str, recurrence_id: datetime) -> CalEvent | None:
        """Return the detached occurrence matching uid + recurrence_id within this calendar, or None."""
        event: CalEvent | None = self._repo_event.find_by_recurrence_id(self._calendar.key, uid, recurrence_id)
        if event is not None and self._calendar.timezone:
            event.calendar_timezone = self._calendar.timezone
        return event

    def get_or_create_occurrence(self, master: CalEvent, recurrence_id: datetime) -> CalEvent:
        """Return the detached occurrence for recurrence_id, creating it if needed."""
        existing: CalEvent | None = self.get_event_by_recurrence_id(master.uid, recurrence_id)
        if existing is not None:
            return existing
        duration: timedelta = master.date_end - master.date_start
        occurrence: CalEvent = dataclasses.replace(
            master,
            key=None,
            db_id=None,
            recurrence_id=recurrence_id,
            recurrence_rule=None,
            recurrence_range=None,
            date_start=recurrence_id,
            date_end=recurrence_id + duration,
            sequence=0,
        )
        return self.insert_event(occurrence)

    @staticmethod
    def _date_end_recurrence(event: CalEvent) -> datetime | None:
        """Return the end datetime of the last occurrence, or None for an unbounded series."""
        if event.recurrence_rule is None:
            return None
        return RruleEngine().get_max_date(event)

    def _upsert_reminder_if_relevant(self, event: CalEvent) -> None:
        """Persist reminders only if the event still has an occurrence in the future.

        Past, non-recurring events (and fully-elapsed series) cannot trigger any reminder,
        so storing rows for them only inflates the table and slows down the active-reminder
        JOIN. When the event has shifted from future to past we still delete any leftover
        rows so the upsert remains idempotent.
        """
        if event.date_start is None:
            self._repo_reminder.delete(event.key)
            return
        now: datetime = datetime.now(timezone.utc)
        if event.recurrence_rule is None:
            has_future: bool = event.date_end is not None and event.date_end >= now
        else:
            max_end: datetime | None = RruleEngine().get_max_date(event)
            # Unbounded series (max_end is None) always have a future occurrence.
            has_future = max_end is None or max_end >= now
        if not has_future:
            self._repo_reminder.delete(event.key)
            return
        self._repo_reminder.upsert(event)

    def _bump_ctag(self) -> None:
        """Increment this calendar's ctag to signal that its event collection has changed.

        CalDAV clients use the CS:getctag extension to detect changes without fetching every event.
        Called automatically by all write operations (insert, update, delete).
        """
        self._calendar.ctag = (self._calendar.ctag or 0) + 1
        self._repo_calendar.update(self._calendar)

    def insert_event(self, event: CalEvent) -> CalEvent:
        """Persist a new event row, bump ctag, and return the event with id and key populated.

        If the event has recurrence_id set, it is treated as a detached occurrence:
        the master event is located by uid to validate it is recurring and to populate parent_uid.
        """
        if event.recurrence_id is not None:
            created: CalEvent = self._insert_detached_occurrence(event)
        else:
            created = self._repo_event.insert(event, self._date_end_recurrence(event))
        if self._calendar.timezone:
            created.calendar_timezone = self._calendar.timezone
        self._upsert_reminder_if_relevant(created)
        self._bump_ctag()
        return created

    def _insert_detached_occurrence(self, event: CalEvent) -> CalEvent:
        """Validate and insert a detached occurrence, linking it to its master event.

        Adds the recurrence_id to the master's EXDATE list for RFC 5545 / CalDAV
        compatibility. The RruleEngine prioritizes overrides over EXDATE, so the
        detached occurrence will still appear in expansion.
        """
        master = self._repo_event.find_master_by_uid(self._calendar.key, event.uid)
        if master is None:
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_FOUND)
        if master.recurrence_rule is None:
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_NOT_RECURRING)
        event.parent_uid = master.uid
        event.recurrence_rule = None
        created = self._repo_event.insert(event)
        if self._calendar.timezone:
            created.calendar_timezone = self._calendar.timezone
        if event.recurrence_id is not None and event.recurrence_id not in (master.recurrence_exceptions or []):
            master.recurrence_exceptions = list(master.recurrence_exceptions or []) + [event.recurrence_id]
            self._repo_event.update(master, self._date_end_recurrence(master))
        return created

    def update_event(self, event: CalEvent) -> None:
        """Persist changes to an existing event row and bump the calendar ctag."""
        self._repo_event.update(event, self._date_end_recurrence(event))
        self._upsert_reminder_if_relevant(event)
        self._bump_ctag()

    def realign_detached_occurrences(self, uid: str, old_start: datetime, new_start: datetime) -> list[tuple[CalEvent, EventAction]]:
        """Realign all detached occurrences to the new master time.

        Shifts the recurrence_id (slot marker) by the master delta while preserving
        any individual time offset the user applied to this occurrence.
        Content changes (title, color, etc.) are untouched.
        Returns a list of (CalEvent, EventAction.UPDATE) for each realigned occurrence.
        """
        delta: timedelta = new_start - old_start
        detached: list[CalEvent] = self._repo_event.find_detached_occurrences(self._calendar.key, uid)
        touched: list[tuple[CalEvent, EventAction]] = []
        for occ in detached:
            if occ.recurrence_id is not None:
                occ.recurrence_id, occ.date_start, occ.date_end = self._compute_realigned_dates(occ, delta)
            try:
                self._repo_event.update(occ, None)
                touched.append((occ, EventAction.UPDATE))
            except RequestException:
                logger_calendar.warning("Could not realign detached occurrence key=%s (uid=%s)", occ.key, uid)
        return touched

    def propagate_partstat_to_copies(self, event: CalEvent, attendee_email: str, status: AttendeeStatus) -> None:
        """Mirror a single attendee's PARTSTAT change to all other local copies of the event.

        Called after an attendee updates their status so the organizer and other local
        attendees see the updated status immediately, without waiting for an iMIP REPLY.
        """
        other_copies: list[CalEvent] = self._repo_event.find_all_by_uid(
            event.uid, exclude_organizer_calendar_key=self._calendar.key
        )
        for copy in other_copies:
            for attendee in copy.attendees:
                if attendee.email == attendee_email:
                    attendee.status = status
                    break
            try:
                self._repo_event.update(copy, self._date_end_recurrence(copy))
            except RequestException:
                logger_calendar.warning(
                    "Could not propagate PARTSTAT to calendar %s (uid=%s)", copy.calendar_key, event.uid
                )

    def split_event(self, uid: str, until: datetime, from_dt: datetime) -> list[tuple[CalEvent, EventAction]]:
        """Truncate a recurring series within this calendar at `until` and soft-delete future detached occurrences.

        COUNT is replaced by UNTIL because after the split the number of occurrences
        remaining in the original series changes, making COUNT semantically wrong per
        RFC 5545 §3.3.10 (COUNT and UNTIL are mutually exclusive).

        Returns a list of (CalEvent, EventAction) for every row modified or deleted:
        the master (UPDATE) followed by each soft-deleted detached occurrence (DELETE).
        """
        master: CalEvent | None = self._repo_event.find_master_by_uid(self._calendar.key, uid)
        if master is None or master.recurrence_rule is None:
            return []
        master.recurrence_rule.until = until
        master.recurrence_rule.count = None
        self._repo_event.update(master, RruleEngine().get_max_date(master))
        self._upsert_reminder_if_relevant(master)
        touched: list[tuple[CalEvent, EventAction]] = [(master, EventAction.UPDATE)]

        detached: list[CalEvent] = self._repo_event.find_detached_occurrences(self._calendar.key, uid)
        for occ in detached:
            if occ.recurrence_id is not None and occ.recurrence_id >= from_dt:
                self._repo_event.delete_by_key(self._calendar.key, occ.key)
                self._repo_reminder.delete(occ.key)
                touched.append((occ, EventAction.DELETE))
        if len(touched) > 1:
            logger_calendar.debug("Soft-deleted %d future detached occurrence(s) for uid=%s", len(touched) - 1, uid)
        self._bump_ctag()
        return touched

    def add_exdate(self, uid: str, dt: datetime) -> None:
        """Add dt to the master's EXDATE within this calendar to suppress a single occurrence.

        Called on the organizer's calendar directly and on each local attendee's calendar
        when an occurrence is cancelled.
        RFC 5545 §3.8.5.1: EXDATE lists datetime values excluded from RRULE expansion.
        """
        master: CalEvent | None = self._repo_event.find_master_by_uid(self._calendar.key, uid)
        if master is None:
            return
        if dt not in (master.recurrence_exceptions or []):
            master.recurrence_exceptions = list(master.recurrence_exceptions or []) + [dt]
            self._repo_event.update(master, self._date_end_recurrence(master))
        self._bump_ctag()

    def delete_event(self, uid: str) -> None:
        """Soft-delete an event by UID within this calendar only and bump ctag.

        Used when an attendee removes their own copy (local operation only).
        Reminders are not cleaned up here because soft-deleted events are filtered
        out by find_pending callers. Hard-delete via purge_deleted handles full cleanup.
        """
        self._repo_event.delete(self._calendar.key, uid)
        self._bump_ctag()


    def delete_by_key(self, key: str) -> None:
        """Soft-delete a single event row by its opaque key and bump ctag."""
        self._repo_event.delete_by_key(self._calendar.key, key)
        self._repo_reminder.delete(key)
        self._bump_ctag()

    def delete_detached_occurrence(self, occurrence: CalEvent) -> None:
        """Soft-delete a detached occurrence, add its recurrence_id to the master EXDATE, and bump ctag.

        Adding to EXDATE prevents the original slot from reappearing in RRULE expansion
        after the detached row is gone.
        """
        master: CalEvent | None = self._repo_event.find_master_by_uid(self._calendar.key, occurrence.uid)
        if master is not None and occurrence.recurrence_id not in (master.recurrence_exceptions or []):
            master.recurrence_exceptions = list(master.recurrence_exceptions or []) + [occurrence.recurrence_id]
            self._repo_event.update(master, self._date_end_recurrence(master))
        self._repo_event.delete_by_key(self._calendar.key, occurrence.key)
        self._repo_reminder.delete(occurrence.key)
        self._bump_ctag()
