from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CalSyncResult:
    """Result of an external calendar synchronization or .ics import.

    ``skipped`` counts entries present in the payload that the engine chose to ignore
    (e.g. orphan detached occurrences whose master is missing - RFC 5545 §3.8.4.4
    considers these invalid). They are intentionally not part of ``total``, which only
    reflects entries the engine actually attempted to materialize.
    """

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    total: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return the counters as a plain dict, as carried in an Agent job result (Redis transport)."""
        return asdict(self)
