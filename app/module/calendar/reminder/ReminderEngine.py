from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.rrule.RruleEngine import RruleEngine

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class ReminderEngine:
    """Computes which reminders are currently active.

    A reminder is active from trigger_at (= event.date_start - minutes_before)
    until event.date_end + lookahead. For recurring events, occurrences are
    expanded and each occurrence is checked independently.
    """

    def __init__(self) -> None:
        self._rrule_engine = RruleEngine()

    def compute_active(
        self,
        reminder_rows: list[dict],
        events_by_key: dict[str, CalEvent],
        now: datetime,
        lookahead_minutes: int = 0,
    ) -> list[CalEventReminder]:
        """Return reminders that are currently active.

        :param reminder_rows: Dicts from RepositoryReminder.find_pending (JOIN result with dates/is_recurring).
        :param events_by_key: Full CalEvent objects keyed by event_key (for title/location and RRULE expansion).
        :param now: Current UTC datetime.
        :param lookahead_minutes: Extra minutes added after event end before the reminder expires.
        """
        lookahead: timedelta = timedelta(minutes=lookahead_minutes)
        results: list[CalEventReminder] = []
        for row in reminder_rows:
            event: CalEvent | None = events_by_key.get(row["event_key"])
            if event is None:
                continue

            minutes_before: int = row["minutes_before"]
            method: ReminderMethod = ReminderMethod(row["method"])

            if row["is_recurring"]:
                results.extend(self._expand_recurring(row, event, method, minutes_before, now, lookahead))
            else:
                if self._is_active(row["trigger_at"], row["date_end"], now, lookahead):
                    results.append(self._event_to_model(row, event, method, minutes_before, row["trigger_at"]))

        return results

    def _expand_recurring(
        self,
        row: dict,
        master: CalEvent,
        method: ReminderMethod,
        minutes_before: int,
        now: datetime,
        lookahead: timedelta,
    ) -> list[CalEventReminder]:
        """Expand a recurring event and return active reminders for each occurrence."""
        expand_start: datetime = now - timedelta(minutes=minutes_before)
        duration: timedelta = (master.date_end - master.date_start) if master.date_end and master.date_start else timedelta(0)
        expand_end: datetime = now + duration + timedelta(minutes=minutes_before) + lookahead

        occurrences: list[CalEvent] = self._rrule_engine.expand(master, expand_start, expand_end)
        results: list[CalEventReminder] = []
        for occ in occurrences:
            occ_trigger: datetime = occ.date_start - timedelta(minutes=minutes_before)
            if self._is_active(occ_trigger, occ.date_end, now, lookahead):
                results.append(self._event_to_model(row, occ, method, minutes_before, occ_trigger))
        return results

    @staticmethod
    def _is_active(trigger_at: datetime, date_end: datetime | None, now: datetime, lookahead: timedelta) -> bool:
        """A reminder is active from trigger_at until event.date_end + lookahead."""
        if trigger_at > now:
            return False
        if date_end is not None and (date_end + lookahead) < now:
            return False
        return True

    @staticmethod
    def _event_to_model(row: dict, event: CalEvent, method: ReminderMethod, minutes_before: int, trigger_at: datetime) -> CalEventReminder:
        """Build a CalEventReminder from a JOIN row and a full CalEvent."""
        return CalEventReminder(
            event_key=row["event_key"],
            title=event.title,
            location=event.location,
            date_start=event.date_start,
            date_end=event.date_end,
            timezone=event.timezone,
            calendar_timezone=getattr(event, "calendar_timezone", None),
            method=method,
            minutes_before=minutes_before,
            trigger_at=trigger_at,
        )
