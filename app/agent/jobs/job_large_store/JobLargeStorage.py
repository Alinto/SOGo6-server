"""Enum listing the backends supported by ``JobLargeStore``."""
from __future__ import annotations

from enum import StrEnum


class JobLargeStorage(StrEnum):
    """Where jobs store payloads too large for ``JobState.result``."""

    IN_MEMORY = "in_memory"   # current backend: Redis via sogo_cache(); swappable later.
    FILE = "file"             # local filesystem under SOGO_P_TMP_PATH; needs a shared
                              # volume across containers if Flask and the agent are split.
