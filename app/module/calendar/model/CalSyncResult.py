from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalSyncResult:
    """Result of an external calendar synchronization."""

    inserted: int
    updated: int
    deleted: int
    total: int
