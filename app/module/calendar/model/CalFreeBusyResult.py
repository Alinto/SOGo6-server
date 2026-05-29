from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod


@dataclass
class CalFreeBusyResult:
    """Aggregated free/busy computation result for a set of attendees."""

    periods_by_uid: dict[str, list[CalFreeBusyPeriod]]
    start: datetime
    end: datetime
