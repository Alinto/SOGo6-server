from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalEventSyncMeta:
    """Lightweight metadata for sync diff — avoids loading full event blobs."""

    db_id: int
    key: str
    uid: str
    recurrence_id: datetime | None
    sequence: int
    updated_at: datetime | None
