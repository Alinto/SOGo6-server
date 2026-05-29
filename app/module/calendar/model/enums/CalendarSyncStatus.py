from __future__ import annotations

from enum import Enum


class CalendarSyncStatus(Enum):
    """Status of an external calendar synchronization task."""

    UNDEFINED = "undefined"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
