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

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent


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

    @staticmethod
    def _date_end_recurrence(event: CalEvent) -> datetime | None:
        """Return the end datetime of the last occurrence, or None for an unbounded series."""
        if event.recurrence_rule is None:
            return None
        return RruleEngine().get_max_date(event)

    def insert_event(self, event: CalEvent) -> CalEvent:
        """Persist a new event row and return it with id and key populated.

        If the event has recurrence_id set, it is treated as a detached occurrence:
        the master event is located by uid to validate it is recurring and to populate parent_uid.
        """
        if event.recurrence_id is not None:
            return self._insert_detached_occurrence(event)
        created = self._repo_event.insert(event, self._date_end_recurrence(event))
        if self._calendar.timezone:
            created.calendar_timezone = self._calendar.timezone
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

    def update_event(self, event: CalEvent) -> None:
        """Persist changes to an existing event row."""
        self._repo_event.update(event, self._date_end_recurrence(event))

    def delete_event(self, uid: str) -> None:
        """Soft-delete an event by UID within this calendar."""
        self._repo_event.delete(self._calendar.key, uid)

    def delete_detached_occurrence(self, occurrence: CalEvent) -> None:
        """Soft-delete a detached occurrence and add its recurrence_id to the master EXDATE.

        Adding to EXDATE prevents the original slot from reappearing in RRULE expansion
        after the detached row is gone.
        """
        master = self._repo_event.find_master_by_uid(self._calendar.key, occurrence.uid)
        if master is not None and occurrence.recurrence_id not in master.recurrence_exceptions:
            master.recurrence_exceptions = list(master.recurrence_exceptions) + [occurrence.recurrence_id]
            self._repo_event.update(master, self._date_end_recurrence(master))
        self._repo_event.delete_by_key(self._calendar.key, occurrence.key)
