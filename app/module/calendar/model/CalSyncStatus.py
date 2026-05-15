from __future__ import annotations

from dataclasses import dataclass

from app.module.calendar.model.enums.CalendarSyncStatus import CalendarSyncStatus


@dataclass
class CalSyncStatus:
    """Status of an external calendar synchronization."""

    sync_status: CalendarSyncStatus
    last_sync: str | None
    sync_error: str | None
