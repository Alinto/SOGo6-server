from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus


@dataclass
class CalOrganizer:
    """
    Organizer of a calendar event (RFC 5545 §3.8.4.3 ORGANIZER).
    """
    # RFC 5545 §3.3.3 CAL-ADDRESS - mailto: URI of the organizer
    email: str
    # RFC 5545 §3.2.2 CN parameter - common name for display
    name: str | None = None
    # RFC 5545 §3.2.16 ROLE parameter - organizational role (e.g. CHAIR)
    role: AttendeeRole | None = None
    # RFC 5545 §3.2.12 PARTSTAT parameter - participation status of the organizer
    status: AttendeeStatus | None = None
    # RFC 5545 §3.2.18 SENT-BY parameter - acting on behalf of another calendar user
    sent_by: str | None = None
    # RFC 5545 §3.2.6 DIR parameter - URI to a directory entry (e.g. ldap://...)
    dir_ref: str | None = None
