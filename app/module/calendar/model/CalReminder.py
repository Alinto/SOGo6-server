from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.ReminderMethod import ReminderMethod


@dataclass
class CalReminder:
    """
    Reminder (alarm) associated with a calendar event (RFC 5545 §3.6.6 VALARM).
    """
    # RFC 5545 §3.8.6.1 ACTION — delivery method for the alarm
    method: ReminderMethod
    # RFC 5545 §3.8.6.3 TRIGGER — offset in minutes before the event start (negative = before)
    minutes_before: int
