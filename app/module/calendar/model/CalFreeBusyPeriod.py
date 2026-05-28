from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.module.calendar.model.enums.FreeBusyType import FreeBusyType


@dataclass
class CalFreeBusyPeriod:
    """A single free/busy time period."""

    date_start: datetime
    date_end: datetime
    fb_type: FreeBusyType
    title: str | None = None
