from __future__ import annotations

from enum import Enum


class EventVisibility(Enum):
    """
    Visibility of a calendar event to other users (RFC 5545 CLASS).
    """
    UNDEFINED = "undefined"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"
