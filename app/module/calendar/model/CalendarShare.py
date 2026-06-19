from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.CalendarPermissions import CalendarPermissions


@dataclass
class CalendarShare(CalendarPermissions):
    """Represents a sharing rule for a calendar - serializable to JSON.

    Extends CalendarPermissions with the target user and calendar context.
    Will be managed by the future ACL module. No dedicated DB table for now.
    """

    user_uid: str = ""
    calendar_key: str = ""
