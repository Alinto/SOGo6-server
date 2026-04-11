from __future__ import annotations

from dataclasses import dataclass, field

from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType


@dataclass
class CalAttendee:  # pylint: disable=too-many-instance-attributes
    """
    Attendee of a calendar event (RFC 5545 ATTENDEE).
    """
    email: str
    name: str | None = None
    role: AttendeeRole = field(default=AttendeeRole.REQUIRED)
    status: AttendeeStatus = field(default=AttendeeStatus.NEEDS_ACTION)
    rsvp: bool = False
    cutype: CalUserType = field(default=CalUserType.INDIVIDUAL)
    delegated_from: str | None = None
    delegated_to: str | None = None
    sent_by: str | None = None
    dir_ref: str | None = None
