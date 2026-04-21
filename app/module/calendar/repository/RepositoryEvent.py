from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL
    from app.module.calendar.model.CalEvent import CalEvent


class RepositoryEvent:
    """Handles all DB reads and writes for sogo_events."""

    def __init__(self, db: ClientSQL) -> None:
        self._db = db

    def find_by_calendar(self, calendar_id: int, start: datetime, end: datetime) -> list[CalEvent]:
        """Return all events for a calendar within [start, end]."""
        # TODO  # pylint: disable=fixme
        raise NotImplementedError

    def insert(self, event: CalEvent) -> CalEvent:
        """Persist a new event and return it with id and key populated."""
        # TODO  # pylint: disable=fixme
        raise NotImplementedError

    def update(self, event: CalEvent) -> None:
        """Update an existing event. event.id must be set."""
        # TODO  # pylint: disable=fixme
        raise NotImplementedError

    def delete(self, calendar_id: int, uid: str) -> None:
        """Soft-delete an event by uid within a calendar."""
        # TODO  # pylint: disable=fixme
        raise NotImplementedError

    def delete_all(self, calendar_id: int) -> None:
        """Soft-delete all events belonging to a calendar."""
        # TODO  # pylint: disable=fixme
        raise NotImplementedError
