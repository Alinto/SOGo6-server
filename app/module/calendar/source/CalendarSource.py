from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.module.calendar.rrule.RecurrenceScopeProcessor import EventAction
from app.module.calendar.rrule.RruleEngine import RruleEngine
from app.utils import errors as err
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus

_DEFAULT_START: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEFAULT_END_SEARCH: datetime = datetime(9999, 12, 31, tzinfo=timezone.utc)


class CalendarSource(ABC):  # pylint: disable=too-many-public-methods
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
        expand: bool = True,
    ) -> list[CalEvent]:
        """Return events overlapping [start, end], sorted by date_start ASC.

        With ``expand=True`` (default): resolve bounds -> fetch -> expand recurring -> filter.
        With ``expand=False`` (export): recurring masters keep their RRULE and are returned
        as-is - no expansion, no Python date filter (the SQL fetch already bounds the range)
        so the recipient calendar can rebuild the series. The upper bound also defaults to
        ``9999-12-31`` in that mode to capture future occurrences.

        start defaults to 1970-01-01 UTC. end defaults to now UTC for an expanded query
        without search, or to 9999-12-31 for a search / raw query. Naive datetimes are UTC.
        """
        return self._collect(self._fetch_events, start, end, search, expand)

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
        expand: bool = True,
    ) -> list[CalEvent]:
        """Return tasks (VTODO) overlapping [start, end], sorted by date_start ASC.

        Same resolution and filtering pipeline as :meth:`get_events`, applied to VTODO
        components. ``expand`` has the same meaning.
        """
        return self._collect(self._fetch_tasks, start, end, search, expand)

    def _collect(
        self,
        fetch: Callable[[datetime, datetime, str | None], list[CalEvent]],
        start: datetime | None,
        end: datetime | None,
        search: str | None,
        expand: bool,
    ) -> list[CalEvent]:
        """Shared pipeline for get_events / get_tasks: resolve bounds, fetch, optionally expand, filter, sort."""
        resolved_start: datetime = start if start is not None else _DEFAULT_START
        if end is not None:
            resolved_end: datetime = end
        elif search is not None or not expand:
            resolved_end = _DEFAULT_END_SEARCH
        else:
            resolved_end = datetime.now(timezone.utc)

        resolved_start = to_utc(resolved_start)
        resolved_end = to_utc(resolved_end)

        raw: list[CalEvent] = fetch(resolved_start, resolved_end, search)
        if expand:
            raw = self._expand_recurring(raw, resolved_start, resolved_end)
            raw = self._filter(raw, resolved_start, resolved_end, search)
        raw.sort(key=lambda e: e.date_start or _DEFAULT_START)
        self._stamp_calendar_tz(raw)
        return raw

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
                overrides_by_uid.setdefault(event.require_uid, []).append(event)
            elif event.recurrence_rule is not None:
                masters.append(event)
            else:
                singles.append(event)

        result: list[CalEvent] = list(singles)
        for master in masters:
            result.extend(
                self._rrule_engine.expand(
                    master, start, end, overrides_by_uid.get(master.require_uid)
                )
            )
        return result

    def _filter(
        self,
        events: list[CalEvent],
        start: datetime,
        end: datetime,
        search: str | None,
    ) -> list[CalEvent]:
        """Apply date-range then optional full-text search filters.

        These filters are applied after RRULE expansion. DB-backed sources already
        pre-filter at the series level (date_end_recurrence), but individual occurrences
        generated by expansion must still be checked against the exact bounds.
        For non-recurring events and search, the Python pass is redundant but harmless.
        """
        result: list[CalEvent] = self._filter_date_start(events, start)
        result = self._filter_date_end(result, end)
        if search:
            result = self.search(result, search)
        return result

    def _filter_date_start(self, events: list[CalEvent], start: datetime) -> list[CalEvent]:
        """Keep events that end at or after start (not already finished).

        A task with no due date has no end, so it never counts as finished and is kept.
        """
        return [e for e in events if e.date_end is None or e.date_end >= start]

    def _filter_date_end(self, events: list[CalEvent], end: datetime) -> list[CalEvent]:
        """Keep events that start at or before end (not in the future)."""
        return [e for e in events if e.require_date_start <= end]

    def search(self, events: list[CalEvent], query: str) -> list[CalEvent]:
        """Keep events matching query in title, description or location.

        Matching is case-insensitive and accent-insensitive: "etape" matches an accented "Etape".
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

    def get_master_event_by_uid(self, uid: str) -> CalEvent | None:
        """Return the master event (recurrence_id IS NULL) matching the given UID, or None if not found."""
        return None

    def get_event_by_recurrence_id(self, uid: str, recurrence_id: datetime) -> CalEvent | None:
        """Return the detached occurrence matching uid + recurrence_id, or None."""
        return None

    def get_sync_metadata(self) -> list:
        """Return lightweight sync metadata for every event. Empty on sources without sync support."""
        return []

    @staticmethod
    def _compute_realigned_dates(
        occ: CalEvent, delta: timedelta,
    ) -> tuple[datetime, datetime, datetime | None]:
        """Compute the realigned recurrence_id, date_start and date_end for a detached occurrence.

        Shifts recurrence_id by the master delta while preserving the individual time offset
        the user may have applied to this occurrence. Returns (new_recurrence_id, new_start, new_end).
        A task occurrence with no due date keeps new_end at None.
        """
        occ_duration: timedelta = occ.duration
        new_recurrence_id: datetime = occ.require_recurrence_id + delta
        time_offset: timedelta = occ.require_date_start - occ.require_recurrence_id
        new_start: datetime = new_recurrence_id + time_offset
        new_end: datetime | None = new_start + occ_duration if occ.date_end is not None else None
        return new_recurrence_id, new_start, new_end

    def realign_detached_occurrences(self, uid: str, old_start: datetime, new_start: datetime) -> list[tuple[CalEvent, EventAction]]:
        """Realign detached occurrences to the new master time.

        No-op on read-only sources. Returns an empty list.
        """
        return []

    def get_or_create_occurrence(self, master: CalEvent, recurrence_id: datetime) -> CalEvent:
        """Return the detached occurrence for recurrence_id, creating it if needed.

        Raises NOT_SUPPORTED on read-only sources.
        """
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def insert_event(self, event: CalEvent) -> CalEvent:
        """Persist a new event. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def update_event(self, event: CalEvent) -> None:
        """Update an existing event. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def update_event_or_fail(self, event: CalEvent, context: str) -> CalEvent:
        """Persist an event update and return it, re-wrapping unexpected errors.

        `context` is a short present-participle phrase used in the failure log
        (e.g. "updating personal fields", "processing iMIP reply").
        """
        try:
            self.update_event(event)
            return event
        except RequestException:
            raise
        except Exception as exc:
            logger_calendar.exception("Unexpected error %s for event %s", context, event.key)
            raise RequestException(error=err.ERROR_CALENDAR_EVENT_UPDATE_FAILED) from exc

    def delete_event(self, uid: str) -> None:
        """Soft-delete an event by uid. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def delete_by_key(self, key: str) -> None:
        """Soft-delete a single event by its opaque key. Raises NOT_SUPPORTED on read-only sources."""
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def delete_occurrence(self, occurrence: CalEvent) -> None:
        """Soft-delete a detached occurrence and add its recurrence_id to the master EXDATE.

        Called instead of delete_event when the event being deleted has recurrence_id set.
        Raises NOT_SUPPORTED on read-only sources.
        """
        raise RequestException(error=err.ERROR_CALENDAR_NOT_SUPPORTED)

    def split_event(self, uid: str, until: datetime, from_dt: datetime) -> list[tuple[CalEvent, EventAction]]:
        """Truncate a recurring series at `until` and soft-delete future detached occurrences.

        Called on the organizer's and each attendee's source as part of a THISANDFUTURE split.
        No-op on read-only sources - only DB-backed sources hold mutable recurring events.
        Returns a list of (CalEvent, EventAction) for every row touched.
        """
        return []

    def add_exdate(self, uid: str, dt: datetime) -> None:
        """Add dt to the master's EXDATE list to suppress a single occurrence slot.

        RFC 5545 §3.8.5.1: EXDATE excludes specific datetime instances from RRULE expansion.
        No-op on read-only sources.
        """

    def propagate_partstat_to_copies(self, event: CalEvent, attendee_email: str, status: AttendeeStatus) -> None:
        """Propagate an attendee's PARTSTAT change to all other local copies of the event.

        No-op on read-only sources. DB-backed sources mirror the status update to every
        other copy sharing the same UID (organizer + other local attendees).
        """
