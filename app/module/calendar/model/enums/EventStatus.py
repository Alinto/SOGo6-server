from __future__ import annotations

from enum import Enum


class EventStatus(Enum):
    """
    Confirmation status of a calendar event (RFC 5545 STATUS).
    """
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"
