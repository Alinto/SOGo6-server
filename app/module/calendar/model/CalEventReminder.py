from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.module.calendar.model.enums.ReminderMethod import ReminderMethod


@dataclass
class CalEventReminder:  # pylint: disable=too-many-instance-attributes
    """Lightweight projection of an active reminder with minimal event context."""

    event_key: str
    title: str | None
    location: str | None
    date_start: datetime | None
    date_end: datetime | None
    timezone: str | None
    calendar_timezone: str | None
    method: ReminderMethod
    minutes_before: int
    trigger_at: datetime
    # Owner of the parent calendar. Populated by the repository so the periodic email-reminder sweep
    # (cross-user) knows whom to notify; left at its default on the per-user path, which already knows.
    user_uid: str | None = None
