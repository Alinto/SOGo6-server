from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.utils.exceptions import BugException


@dataclass
class CalReminder:
    """
    Reminder (alarm) associated with a calendar event (RFC 5545 §3.6.6 VALARM).
    """
    # RFC 5545 §3.8.6.1 ACTION — delivery method for the alarm
    method: ReminderMethod
    # RFC 5545 §3.8.6.3 TRIGGER — offset in minutes before the event start (negative = before).
    # None means "not specified by the caller": the offset is then resolved from the parent
    # calendar's default (default_alarm_duration_min) or the global fallback before persistence.
    minutes_before: int | None = None

    @property
    def require_minutes_before(self) -> int:
        """Resolved trigger offset, guaranteed set once defaults have been applied.

        See CalEvent.resolve_reminder_offsets, run on every create/update before persistence.
        """
        if self.minutes_before is None:
            raise BugException("CalReminder.minutes_before accessed before its default was resolved")
        return self.minutes_before
