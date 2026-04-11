from __future__ import annotations

from enum import Enum


class AttendeeRole(Enum):
    """
    Participation role of an attendee in a calendar event (RFC 5545 ROLE).
    """
    CHAIR = "chair"
    REQUIRED = "required"
    OPTIONAL = "optional"
    NON_PARTICIPANT = "non-participant"
