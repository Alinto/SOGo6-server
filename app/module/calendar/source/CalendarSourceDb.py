from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.module.calendar.repository.RepositoryCalendar import RepositoryCalendar
from app.module.calendar.repository.RepositoryEvent import RepositoryEvent
from app.module.calendar.source.CalendarSource import CalendarSource

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
        self._calendar = self._repo_calendar.insert(calendar)
        return self._calendar

    def update_calendar(self, calendar: CalCalendar) -> None:
        self._repo_calendar.update(calendar)
        self._calendar = calendar

    def delete_calendar(self) -> None:
        self._repo_event.delete_all(self._calendar.id)
        self._repo_calendar.delete(self._calendar.id)

    def _fetch_events(self, start: datetime, end: datetime) -> list[CalEvent]:
        return self._repo_event.find_by_calendar(self._calendar.id, start, end)

    def insert_event(self, event: CalEvent) -> CalEvent:
        return self._repo_event.insert(event)

    def update_event(self, event: CalEvent) -> None:
        self._repo_event.update(event)

    def delete_event(self, uid: str) -> None:
        self._repo_event.delete(self._calendar.id, uid)
