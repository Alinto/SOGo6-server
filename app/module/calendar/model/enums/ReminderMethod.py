from __future__ import annotations

from enum import Enum


class ReminderMethod(Enum):
    """
    Delivery method for a calendar event reminder (RFC 5545 VALARM ACTION).
    """
    POPUP = "popup"
    EMAIL = "email"
