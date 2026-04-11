from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.ReminderMethod import ReminderMethod


@dataclass
class CalReminder:
    """
    Reminder associated with a calendar event (RFC 5545 VALARM).
    """
    method: ReminderMethod
    minutes_before: int
