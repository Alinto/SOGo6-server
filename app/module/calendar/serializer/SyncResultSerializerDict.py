from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalSyncResult import CalSyncResult
from app.module.calendar.serializer.Serializer import Serializer


class SyncResultSerializerDict(Serializer[CalSyncResult, dict[str, Any]]):
    """Serializes a CalSyncResult to a dict for API responses."""

    def serialize(self, data: CalSyncResult) -> dict[str, Any]:
        return {
            "inserted": data.inserted,
            "updated": data.updated,
            "deleted": data.deleted,
            "total": data.total,
            "skipped": data.skipped,
        }
