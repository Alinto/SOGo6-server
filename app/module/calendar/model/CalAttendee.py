from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType


@dataclass
class CalAttendee:  # pylint: disable=too-many-instance-attributes
    """
    Attendee of a calendar event (RFC 5545 §3.8.4.1 ATTENDEE).
    """
    # RFC 5545 §3.3.3 CAL-ADDRESS - mailto: URI of the attendee
    email: str
    # RFC 5545 §3.2.2 CN parameter - common name for display
    name: str | None = None
    # RFC 5545 §3.2.16 ROLE parameter - participation role
    role: AttendeeRole = field(default=AttendeeRole.REQUIRED)
    # RFC 5545 §3.2.12 PARTSTAT parameter - participation status
    status: AttendeeStatus = field(default=AttendeeStatus.NEEDS_ACTION)
    # RFC 5545 §3.2.17 RSVP parameter - reply requested
    rsvp: bool = False
    # RFC 5545 §3.2.3 CUTYPE parameter - calendar user type
    cutype: CalUserType = field(default=CalUserType.INDIVIDUAL)
    # RFC 5545 §3.2.4 DELEGATED-FROM parameter - who delegated to this attendee
    delegated_from: str | None = None
    # RFC 5545 §3.2.5 DELEGATED-TO parameter - who this attendee delegated to
    delegated_to: str | None = None
    # RFC 5545 §3.2.18 SENT-BY parameter - acting on behalf of
    sent_by: str | None = None
    # RFC 5545 §3.2.6 DIR parameter - URI to directory entry (e.g. LDAP)
    dir_ref: str | None = None
