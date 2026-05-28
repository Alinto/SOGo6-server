from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.utils.calendar.DateTimeUtils import resolve_tz

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

# Weekdays considered non-working (weekday() convention: Monday=0 … Sunday=6).
# Saturday=5, Sunday=6.
# TODO: Check if this can be defined by users  # pylint: disable=fixme
_NON_WORKING_WEEKDAYS: frozenset[int] = frozenset({5, 6})

_SHOW_AS_TO_FB_TYPE: dict[ShowAs, FreeBusyType] = {
    ShowAs.BUSY: FreeBusyType.BUSY,
    ShowAs.OUT_OF_OFFICE: FreeBusyType.UNAVAILABLE,
    ShowAs.TENTATIVE: FreeBusyType.TENTATIVE,
}


@dataclass
class FreeBusyPrefs:
    """User preferences that influence FreeBusy computation."""

    busy_off_hours: bool = False
    workday_start: str = "09:00"   # HH:MM in the user's local timezone
    workday_end: str = "18:00"     # HH:MM in the user's local timezone
    timezone: str = "UTC"          # IANA timezone name (SOGO_U_TIMEZONE)


class FreeBusyEngine:
    """Computes free/busy periods from a list of calendar events."""

    def compute(
        self,
        events: list[CalEvent],
        start: datetime,
        end: datetime,
        prefs: FreeBusyPrefs,
    ) -> list[CalFreeBusyPeriod]:
        """Return merged, sorted free/busy periods for the given event list.

        Events with show_as=free or status=cancelled are excluded.
        If prefs.busy_off_hours is True, periods outside working hours and on
        non-working days are added as UNAVAILABLE.
        """
        periods: list[CalFreeBusyPeriod] = []

        for event in events:
            # Cancelled events are never busy regardless of show_as
            if event.status == EventStatus.CANCELLED:
                continue
            # show_as=free has no mapping and is excluded
            fb_type = _SHOW_AS_TO_FB_TYPE.get(event.show_as)
            if fb_type is None:
                continue
            # Clip the event to the queried range; discard zero-duration results
            clipped_start = max(event.date_start, start)
            clipped_end = min(event.date_end, end)
            if clipped_start >= clipped_end:
                continue
            # Expose the title only for public events
            title = event.title if event.visibility == EventVisibility.PUBLIC else None
            periods.append(CalFreeBusyPeriod(
                date_start=clipped_start,
                date_end=clipped_end,
                fb_type=fb_type,
                title=title,
            ))

        if prefs.busy_off_hours:
            user_tz = resolve_tz(prefs.timezone)
            work_start = self._parse_time(prefs.workday_start)
            work_end = self._parse_time(prefs.workday_end)
            periods.extend(self._unavailable_periods(start, end, work_start, work_end, user_tz))

        return self._merge(periods)

    def _unavailable_periods(  # pylint: disable=too-many-locals
        self,
        start: datetime,
        end: datetime,
        work_start: time,
        work_end: time,
        user_tz: ZoneInfo,
    ) -> list[CalFreeBusyPeriod]:
        """Generate UNAVAILABLE periods for time outside working hours."""
        periods: list[CalFreeBusyPeriod] = []

        # Convert to user's local timezone to iterate over calendar days as they appear to the user.
        local_start = start.astimezone(user_tz)
        local_end = end.astimezone(user_tz)
        current_date = local_start.date()

        while current_date <= local_end.date():
            day_start_utc = datetime.combine(current_date, time(0, 0, 0), tzinfo=user_tz).astimezone(timezone.utc)
            day_end_utc = datetime.combine(current_date, time(23, 59, 59), tzinfo=user_tz).astimezone(timezone.utc)

            p_start = max(day_start_utc, start)
            p_end = min(day_end_utc, end)

            if p_start >= p_end:
                current_date += timedelta(days=1)
                continue

            if current_date.weekday() in _NON_WORKING_WEEKDAYS:
                periods.append(CalFreeBusyPeriod(p_start, p_end, FreeBusyType.UNAVAILABLE))
            else:
                work_start_utc = datetime.combine(current_date, work_start, tzinfo=user_tz).astimezone(timezone.utc)
                work_end_utc = datetime.combine(current_date, work_end, tzinfo=user_tz).astimezone(timezone.utc)

                before_end = min(work_start_utc, p_end)
                if p_start < before_end:
                    periods.append(CalFreeBusyPeriod(p_start, before_end, FreeBusyType.UNAVAILABLE))

                after_start = max(work_end_utc, p_start)
                if after_start < p_end:
                    periods.append(CalFreeBusyPeriod(after_start, p_end, FreeBusyType.UNAVAILABLE))

            current_date += timedelta(days=1)

        return periods

    @staticmethod
    def _merge(periods: list[CalFreeBusyPeriod]) -> list[CalFreeBusyPeriod]:
        """Merge overlapping or adjacent periods of the same type, sort by date_start."""
        if not periods:
            return []
        sorted_periods = sorted(periods, key=lambda p: (p.fb_type.value, p.date_start))
        merged: list[CalFreeBusyPeriod] = []
        current = sorted_periods[0]
        for period in sorted_periods[1:]:
            if period.fb_type == current.fb_type and period.date_start < current.date_end:
                merged_title = current.title if current.title == period.title else None
                current = CalFreeBusyPeriod(
                    date_start=current.date_start,
                    date_end=max(current.date_end, period.date_end),
                    fb_type=current.fb_type,
                    title=merged_title,
                )
            else:
                merged.append(current)
                current = period
        merged.append(current)
        merged.sort(key=lambda p: p.date_start)
        return merged

    @staticmethod
    def _parse_time(value: str) -> time:
        """Parse a time string into a datetime.time object.

        Expects 24-hour format HH:MM. Any other format (e.g. AM/PM) raises ValueError.
        # TODO: validate HH:MM format at settings write time to prevent silent failures here.
        """
        h, m = value.split(":")
        return time(int(h), int(m), 0)
