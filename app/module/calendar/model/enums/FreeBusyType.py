from __future__ import annotations

from enum import Enum


class FreeBusyType(Enum):
    """RFC 5545 §3.2.9 free/busy type values."""

    BUSY = "busy"
    TENTATIVE = "tentative"
    UNAVAILABLE = "unavailable"
