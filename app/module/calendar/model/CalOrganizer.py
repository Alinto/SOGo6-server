from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus


@dataclass
class CalOrganizer:
    """
    Organizer of a calendar event (RFC 5545 ORGANIZER).
    role and status are not part of RFC 5545 ORGANIZER but are used in the JSON API
    to represent the organizer's participation role and confirmation status.
    """
    email: str
    name: str | None = None
    role: AttendeeRole | None = None
    status: AttendeeStatus | None = None
    sent_by: str | None = None
    dir_ref: str | None = None
