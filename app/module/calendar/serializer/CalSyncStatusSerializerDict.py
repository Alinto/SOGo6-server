from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalSyncStatus import CalSyncStatus
from app.utils.serializer.Serializer import Serializer


class CalSyncStatusSerializerDict(Serializer[CalSyncStatus, dict[str, Any]]):
    """Serializes a CalSyncStatus to a dict for API responses."""

    def serialize(self, data: CalSyncStatus) -> dict[str, Any]:
        return {
            "sync_status": data.sync_status.value,
            "last_sync": data.last_sync,
            "sync_error": data.sync_error,
        }
