from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalAttachment:
    """
    File or URI attachment associated with a calendar event (RFC 5545 ATTACH).
    """
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    data: bytes | None = None
