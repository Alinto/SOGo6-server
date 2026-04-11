from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.module.calendar.source.CalendarSource import CalendarSource

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarSourceDb(CalendarSource):
    """Calendar source backed by the database (sogo_events table)."""

    def _fetch_events(self, start: datetime, end: datetime) -> list[CalEvent]:
        # TODO: query sogo_events for the given calendar and date range  # pylint: disable=fixme
        raise NotImplementedError
