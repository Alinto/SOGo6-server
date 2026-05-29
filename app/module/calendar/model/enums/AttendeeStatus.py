from __future__ import annotations

from enum import Enum


class AttendeeStatus(Enum):
    """
    Participation status of an attendee in a calendar event (RFC 5545 PARTSTAT).
    """
    NEEDS_ACTION = "needs-action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    DELEGATED = "delegated"
