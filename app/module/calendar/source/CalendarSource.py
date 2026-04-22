from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.module.calendar.rrule.RruleEngine import RruleEngine
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent

_DEFAULT_START: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEFAULT_END_SEARCH: datetime = datetime(9999, 12, 31, tzinfo=timezone.utc)


class CalendarSource(ABC):
    """
    Abstract base class for a calendar event source.

    Subclasses implement _fetch_events() to return raw CalEvent objects.
    This base class handles date bound defaults, UTC normalization,
    RRULE expansion and filtering.
    """

    def __init__(self, calendar: CalCalendar) -> None:
        """Initialise the source with its associated calendar and the RRULE engine."""
        self._calendar = calendar
        self._rrule_engine: RruleEngine = RruleEngine()

    @property
    def calendar(self) -> CalCalendar:
        """The calendar associated with this source."""
        return self._calendar

    def get_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
    ) -> list[CalEvent]:
        """Return events overlapping [start, end], sorted by date_start ASC.

        Pipeline: resolve bounds → fetch raw → expand recurring → filter.
        start defaults to 1970-01-01 UTC.
        end defaults to 9999-12-31 when a search query is provided (no date constraint),
        or to now UTC otherwise.
        Naive datetimes are treated as UTC.
        """
        resolved_start: datetime = start if start is not None else _DEFAULT_START
        if end is not None:
            resolved_end: datetime = end
        elif search is not None:
            resolved_end = _DEFAULT_END_SEARCH
        else:
            resolved_end = datetime.now(timezone.utc)

        if resolved_start.tzinfo is None:
            resolved_start = resolved_start.replace(tzinfo=timezone.utc)
        if resolved_end.tzinfo is None:
            resolved_end = resolved_end.replace(tzinfo=timezone.utc)

        raw: list[CalEvent] = self._fetch_events(resolved_start, resolved_end, search)
        expanded: list[CalEvent] = self._expand_recurring(raw, resolved_start, resolved_end)
        result: list[CalEvent] = self.filter(expanded, resolved_start, resolved_end, search)
        result.sort(key=lambda e: e.date_start)
        self._stamp_calendar_tz(result)
        return result

    @abstractmethod
    def _fetch_events(self, start: datetime, end: datetime, search: str | None = None) -> list[CalEvent]:
        """Return raw CalEvent objects for the given date range.

        Receives non-None UTC-aware datetimes. DB-backed sources may push the search filter
        to SQL; other sources ignore it here and rely on the base class Python filter.
        """
        raise NotImplementedError

    def get_tasks(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
    ) -> list[CalEvent]:
        """Return tasks (VTODO) overlapping [start, end], sorted by date_start ASC.

        Same resolution and filtering pipeline as get_events, applied to VTODO components.
        """
        resolved_start: datetime = start if start is not None else _DEFAULT_START
        if end is not None:
            resolved_end: datetime = end
        elif search is not None:
            resolved_end = _DEFAULT_END_SEARCH
        else:
            resolved_end = datetime.now(timezone.utc)

        if resolved_start.tzinfo is None:
            resolved_start = resolved_start.replace(tzinfo=timezone.utc)
        if resolved_end.tzinfo is None:
            resolved_end = resolved_end.replace(tzinfo=timezone.utc)

        raw: list[CalEvent] = self._fetch_tasks(resolved_start, resolved_end, search)
        expanded: list[CalEvent] = self._expand_recurring(raw, resolved_start, resolved_end)
        result: list[CalEvent] = self.filter(expanded, resolved_start, resolved_end, search)
        result.sort(key=lambda e: e.date_start)
        self._stamp_calendar_tz(result)
        return result

    def _fetch_tasks(self, start: datetime, end: datetime, search: str | None = None) -> list[CalEvent]:
        """Return raw VTODO CalEvent objects. Override in DB-backed sources."""
        return []

    def _expand_recurring(
        self,
        events: list[CalEvent],
        start: datetime,
        end: datetime,
    ) -> list[CalEvent]:
        """Expand recurring master events into individual occurrences."""
        singles: list[CalEvent] = []
        masters: list[CalEvent] = []
        overrides_by_uid: dict[str, list[CalEvent]] = {}

        for event in events:
            if event.recurrence_id is not None:
                overrides_by_uid.setdefault(event.uid, []).append(event)
            elif event.recurrence_rule is not None:
                masters.append(event)
            else:
                singles.append(event)

        result: list[CalEvent] = list(singles)
        for master in masters:
            result.extend(
                self._rrule_engine.expand(
                    master, start, end, overrides_by_uid.get(master.uid)
                )
            )
        return result

    def filter(
        self,
        events: list[CalEvent],
        start: datetime,
        end: datetime,
        search: str | None,
    ) -> list[CalEvent]:
        """Apply date-range then optional full-text search filters."""
        result: list[CalEvent] = self.filter_date_start(events, start)
        result = self.filter_date_end(result, end)
        if search:
            result = self.search(result, search)
        return result

    # TODO: Override with CalendarSourceDb  # pylint: disable=fixme
    def filter_date_start(self, events: list[CalEvent], start: datetime) -> list[CalEvent]:
        """Keep events that end at or after start (not already finished)."""
        return [e for e in events if e.date_end >= start]

    # TODO: Override with CalendarSourceDb  # pylint: disable=fixme
    def filter_date_end(self, events: list[CalEvent], end: datetime) -> list[CalEvent]:
        """Keep events that start at or before end (not in the future)."""
        return [e for e in events if e.date_start <= end]

    # TODO: Override with CalendarSourceDb  # pylint: disable=fixme
    def search(self, events: list[CalEvent], query: str) -> list[CalEvent]:
        """Keep events matching query in title, description or location.

        Matching is case-insensitive and accent-insensitive: "etape" matches "Étape".
        """
        needle: str = self._fold(query)
        return [
            e for e in events
            if needle in self._fold(e.title or "")
            or needle in self._fold(e.description or "")
            or needle in self._fold(e.location or "")
        ]

    @staticmethod
    def _fold(text: str) -> str:
        """Lowercase and strip diacritics for accent-insensitive matching."""
        return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower()

    def _stamp_calendar_tz(self, events: list[CalEvent]) -> None:
        """Stamp calendar_key and calendar_timezone on each event from the associated calendar."""
        key = self._calendar.key
        tz = self._calendar.timezone
        for event in events:
            if key:
                event.calendar_key = key
            if tz:
                event.calendar_timezone = tz

    def is_writable(self) -> bool:
        """Return True if this source supports write operations."""
        return False

    def save_calendar(self, calendar: CalCalendar) -> CalCalendar:
        """Persist a new calendar. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def update_calendar(self, calendar: CalCalendar) -> None:
        """Update calendar metadata. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def delete_calendar(self) -> None:
        """Delete the calendar and all its events. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def get_event(self, event_key: str) -> CalEvent | None:
        """Return a single event by key, or None if not found or not supported by this source."""
        return None

    def insert_event(self, event: CalEvent) -> CalEvent:
        """Persist a new event. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def update_event(self, event: CalEvent) -> None:
        """Update an existing event. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def delete_event(self, uid: str) -> None:
        """Soft-delete an event by uid. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def delete_detached_occurrence(self, occurrence: CalEvent) -> None:
        """Soft-delete a detached occurrence and add its recurrence_id to the master EXDATE.

        Called instead of delete_event when the event being deleted has recurrence_id set.
        Raises NOT_SUPPORTED on read-only sources.
        """
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)
