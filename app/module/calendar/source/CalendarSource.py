from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.module.calendar.rrule.RruleEngine import RruleEngine

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

_DEFAULT_START: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CalendarSource(ABC):
    """
    Abstract base class for a calendar event source.

    Subclasses implement _fetch_events() to return raw CalEvent objects.
    This base class handles date bound defaults, UTC normalization,
    RRULE expansion and filtering.
    """

    def __init__(self) -> None:
        self._rrule_engine: RruleEngine = RruleEngine()

    def get_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
    ) -> list[CalEvent]:
        """Return events overlapping [start, end], sorted by start_date ASC.

        Pipeline: resolve bounds → fetch raw → expand recurring → filter.
        start defaults to 1970-01-01 UTC, end defaults to now UTC.
        Naive datetimes are treated as UTC.
        """
        resolved_start: datetime = start if start is not None else _DEFAULT_START
        resolved_end: datetime = end if end is not None else datetime.now(timezone.utc)

        if resolved_start.tzinfo is None:
            resolved_start = resolved_start.replace(tzinfo=timezone.utc)
        if resolved_end.tzinfo is None:
            resolved_end = resolved_end.replace(tzinfo=timezone.utc)

        raw: list[CalEvent] = self._fetch_events(resolved_start, resolved_end)
        expanded: list[CalEvent] = self._expand_recurring(raw, resolved_start, resolved_end)
        result: list[CalEvent] = self.filter(expanded, resolved_start, resolved_end, search)
        result.sort(key=lambda e: e.start_date)
        return result

    @abstractmethod
    def _fetch_events(self, start: datetime, end: datetime) -> list[CalEvent]:
        """Return raw, unfiltered CalEvent objects for the given date range.

        Receives non-None UTC-aware datetimes. Should return all events
        (masters + overrides + singles) without filtering — the base class handles that.
        """
        raise NotImplementedError

    def _expand_recurring(
        self,
        events: list[CalEvent],
        start: datetime,
        end: datetime,
    ) -> list[CalEvent]:
        """Expand recurring master events into individual occurrences.

        Separates events into singles / overrides (recurrence_id set) / masters (have rule),
        then expands each master via RruleEngine.
        """
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
        return [e for e in events if e.end_date >= start]

    # TODO: Override with CalendarSourceDb  # pylint: disable=fixme
    def filter_date_end(self, events: list[CalEvent], end: datetime) -> list[CalEvent]:
        """Keep events that start at or before end (not in the future)."""
        return [e for e in events if e.start_date <= end]

    # TODO: Override with CalendarSourceDb  # pylint: disable=fixme
    def search(self, events: list[CalEvent], query: str) -> list[CalEvent]:
        """Keep events matching query in title, description or location.

        Matching is case-insensitive and accent-insensitive: "etape" matches "Étape".
        Normalization strips diacritics via NFD decomposition (unicodedata stdlib).
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
