from __future__ import annotations

from enum import Enum


class ShowAs(Enum):
    """
    How the event time is shown in free/busy queries (RFC 5545 TRANSP).
    """
    BUSY = "busy"
    FREE = "free"
    OUT_OF_OFFICE = "out-of-office"
    TENTATIVE = "tentative"
