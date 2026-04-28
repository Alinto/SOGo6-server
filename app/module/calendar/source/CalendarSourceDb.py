from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent
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
        """Soft-delete all events in the calendar, then hard-delete the calendar row."""
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

    @staticmethod
    def _date_end_recurrence(event: CalEvent) -> datetime | None:
        """Return the end datetime of the last occurrence, or None for an unbounded series."""
        if event.recurrence_rule is None:
            return None
        return RruleEngine().get_max_date(event)

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
        self._bump_ctag()
        return created

    def _insert_detached_occurrence(self, event: CalEvent) -> CalEvent:
        """Validate and insert a detached occurrence, linking it to its master event."""
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
        return created

    # Fields propagated from the organizer's copy to attendee copies on event update.
    # Excludes reminders and conference_data — each attendee manages their own.
    _PROPAGATABLE_FIELDS: frozenset[str] = frozenset({
        "title", "description", "location", "url", "date_start", "date_end",
        "all_day", "timezone", "status", "visibility", "show_as", "color",
        "sequence", "organizer", "attendees", "attachments", "categories",
        "related_to", "extra_properties", "recurrence_rule", "recurrence_exceptions", "priority",
    })

    def update_event(self, event: CalEvent, propagate: bool = False) -> None:
        """Persist changes to an existing event row and bump the calendar ctag.

        When propagate is True and the event has an organizer, content changes are
        mirrored to all other local copies of the event (internal attendees in sogo_events).
        """
        self._repo_event.update(event, self._date_end_recurrence(event))
        if propagate and event.organizer:
            self._propagate_organizer_update(event)
        self._bump_ctag()

    def _propagate_organizer_update(self, event: CalEvent) -> None:
        """Mirror organizer content changes to all other local copies of the event.

        Loads each attendee copy sharing the same UID, overwrites the propagatable fields
        with the organizer's values, and re-saves. Failures per copy are logged and skipped
        so that a single bad row does not abort the whole propagation.
        """
        other_copies: list[CalEvent] = self._repo_event.find_all_by_uid(
            event.uid, exclude_organizer_calendar_key=self._calendar.key
        )
        for copy in other_copies:
            for field_name in self._PROPAGATABLE_FIELDS:
                setattr(copy, field_name, getattr(event, field_name))
            try:
                self._repo_event.update(copy, self._date_end_recurrence(copy))
            except RequestException:
                logger_calendar.warning(
                    "Could not propagate event update to calendar %s (uid=%s)", copy.calendar_key, event.uid
                )

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

    def delete_event(self, uid: str) -> None:
        """Soft-delete an event by UID within this calendar only and bump ctag.

        Used when an attendee removes their own copy (local operation only).
        """
        self._repo_event.delete(self._calendar.key, uid)
        self._bump_ctag()

    def delete_event_as_organizer(self, uid: str) -> None:
        """Soft-delete all copies of an event across all local calendars, then bump ctag.

        Called when an organizer cancels an event: removes both the organizer's row
        and every attendee copy sharing the same UID in sogo_events.
        """
        self._repo_event.delete_all_by_uid(uid)
        self._bump_ctag()

    def delete_detached_occurrence(self, occurrence: CalEvent) -> None:
        """Soft-delete a detached occurrence, add its recurrence_id to the master EXDATE, and bump ctag.

        Adding to EXDATE prevents the original slot from reappearing in RRULE expansion
        after the detached row is gone.
        """
        master: CalEvent | None = self._repo_event.find_master_by_uid(self._calendar.key, occurrence.uid)
        if master is not None and occurrence.recurrence_id not in master.recurrence_exceptions:
            master.recurrence_exceptions = list(master.recurrence_exceptions) + [occurrence.recurrence_id]
            self._repo_event.update(master, self._date_end_recurrence(master))
        self._repo_event.delete_by_key(self._calendar.key, occurrence.key)
        self._bump_ctag()
