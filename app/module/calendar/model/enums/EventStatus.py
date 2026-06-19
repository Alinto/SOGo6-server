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

    @classmethod
    def event_values(cls) -> list[str]:
        """STATUS values valid for a VEVENT (RFC 5545 §3.8.1.11)."""
        return [cls.CONFIRMED.value, cls.TENTATIVE.value, cls.CANCELLED.value]

    @classmethod
    def task_values(cls) -> list[str]:
        """STATUS values valid for a VTODO (RFC 5545 §3.8.1.11)."""
        return [cls.NEEDS_ACTION.value, cls.IN_PROCESS.value, cls.COMPLETED.value, cls.CANCELLED.value]
