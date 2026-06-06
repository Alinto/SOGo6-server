"""Typed reference to a stored large blob.

Identifies where a blob lives (``locator``: a filesystem path or a Redis key,
backend-dependent) plus its MIME type. It is the value passed around in a
``JobRequest`` payload (input) or under ``JobState.result`` (output); it travels
on the wire as a plain dict via :meth:`to_dict` / :meth:`from_dict`.

It carries no backend choice: the storage backend is process-wide (set once by
``ClientAgent`` from config), so a reference only needs to say *where*, not *how*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobLargeRef:
    """Where a stored blob lives, plus its content type."""

    content_type: str
    locator: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON-safe dict stored on the wire."""
        return {"content_type": self.content_type, "locator": self.locator}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobLargeRef:
        """Rebuild a reference from its wire dict."""
        return cls(content_type=data["content_type"], locator=data["locator"])
