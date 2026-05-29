from __future__ import annotations

from enum import Enum


class CalUserType(Enum):
    """
    Type of calendar user associated with an attendee (RFC 5545 CUTYPE).
    """
    INDIVIDUAL = "individual"
    GROUP = "group"
    RESOURCE = "resource"
    ROOM = "room"
    UNKNOWN = "unknown"
