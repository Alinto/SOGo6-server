from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CalFreeBusyRequest:
    """Format-agnostic representation of a parsed free/busy request."""

    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    organizer: str | None = None
