from __future__ import annotations

from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb


class CalendarSourceIcsMirror(CalendarSourceDb):
    """DB-backed source for external ICS calendars (read-only mirror).

    Events are populated by the sync engine, not by direct CRUD operations.
    All write attempts from the API are rejected via is_writable() → False.
    The sync engine calls unlock() before writing to temporarily allow writes.
    """

    def __init__(self, db, calendar) -> None:
        super().__init__(db, calendar)
        self._is_writable: bool = False

    def is_writable(self) -> bool:
        return self._is_writable

    def unlock(self) -> None:
        """Allow write operations. Reserved for the sync engine."""
        self._is_writable = True

    def lock(self) -> None:
        """Restore read-only mode after sync."""
        self._is_writable = False
