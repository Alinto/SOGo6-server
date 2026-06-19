"""Owner domain of a stored blob in the shared file storage."""
from __future__ import annotations

from enum import StrEnum


class FileAdapterSource(StrEnum):
    """Which domain owns a stored blob, so co-located uses of the file storage stay isolated.

    The blob store is shared (contact photos, agent job blobs...); each owner stamps its rows with
    its source so per-owner enumeration and purge never reach another owner's blobs.
    """

    CONTACT = "contact"
    AGENT = "agent"
