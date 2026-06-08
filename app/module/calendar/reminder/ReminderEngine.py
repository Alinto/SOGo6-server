from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.module.calendar.model.CalEventReminder import CalEventReminder
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
        reminders: list[CalEventReminder],
        events_by_key: dict[str, CalEvent],
        now: datetime,
        lookahead_minutes: int = 0,
    ) -> list[CalEventReminder]:
        """Return reminders that are currently active.

        :param reminders: CalEventReminder objects from the repository (enriched by the module).
        :param events_by_key: Full CalEvent objects keyed by event_key (for RRULE expansion).
        :param now: Current UTC datetime.
        :param lookahead_minutes: Extra minutes added after event end before the reminder expires.
        """
        lookahead: timedelta = timedelta(minutes=lookahead_minutes)
        results: list[CalEventReminder] = []
        for reminder in reminders:
            event: CalEvent | None = events_by_key.get(reminder.event_key)
            if event is None:
                continue

            if event.recurrence_rule is not None:
                results.extend(self._expand_recurring(reminder, event, now, lookahead))
            else:
                if self._is_active(reminder.trigger_at, reminder.date_end, now, lookahead):
                    results.append(reminder)

        return results

    def _expand_recurring(
        self,
        reminder: CalEventReminder,
        master: CalEvent,
        now: datetime,
        lookahead: timedelta,
    ) -> list[CalEventReminder]:
        """Expand a recurring event and return active reminders for each occurrence."""
        expand_start: datetime = now - timedelta(minutes=reminder.minutes_before)
        duration: timedelta = (master.date_end - master.date_start) if master.date_end and master.date_start else timedelta(0)
        expand_end: datetime = now + duration + timedelta(minutes=reminder.minutes_before) + lookahead

        occurrences: list[CalEvent] = self._rrule_engine.expand(master, expand_start, expand_end)
        results: list[CalEventReminder] = []
        for occ in occurrences:
            occ_trigger: datetime = occ.require_date_start - timedelta(minutes=reminder.minutes_before)
            if self._is_active(occ_trigger, occ.date_end, now, lookahead):
                results.append(CalEventReminder(
                    event_key=reminder.event_key,
                    title=reminder.title,
                    location=reminder.location,
                    date_start=occ.date_start,
                    date_end=occ.date_end,
                    timezone=reminder.timezone,
                    calendar_timezone=reminder.calendar_timezone,
                    method=reminder.method,
                    minutes_before=reminder.minutes_before,
                    trigger_at=occ_trigger,
                ))
        return results

    @staticmethod
    def _is_active(trigger_at: datetime, date_end: datetime | None, now: datetime, lookahead: timedelta) -> bool:
        """A reminder is active from trigger_at until event.date_end + lookahead."""
        if trigger_at > now:
            return False
        if date_end is not None and (date_end + lookahead) < now:
            return False
        return True
