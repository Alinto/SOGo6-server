from __future__ import annotations

from enum import Enum


class EventStatus(Enum):
    """
    Status of a calendar component (RFC 5545 §3.8.1.11 STATUS).

    VEVENT values: CONFIRMED, TENTATIVE, CANCELLED.
    VTODO values: NEEDS_ACTION, IN_PROCESS, COMPLETED, CANCELLED.
    """
    UNDEFINED = "undefined"
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"
    # VTODO-specific statuses
    NEEDS_ACTION = "needs_action"
    IN_PROCESS = "in_process"
    COMPLETED = "completed"
