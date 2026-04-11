from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency


@dataclass
class CalRecurrenceRule:  # pylint: disable=too-many-instance-attributes
    """
    Recurrence rule defining how an event repeats over time (RFC 5545 RRULE).
    """
    frequency: RecurrenceFrequency
    interval: int = 1
    until: datetime | None = None
    count: int | None = None
    by_day: list[str] | None = None
    by_month_day: list[int] | None = None
    by_month: list[int] | None = None
    by_year_day: list[int] | None = None
    by_week_no: list[int] | None = None
    by_set_pos: list[int] | None = None
    by_hour: list[int] | None = None
    by_minute: list[int] | None = None
    by_second: list[int] | None = None
    week_start: str = "MO"
    additional_dates: list[datetime] = field(default_factory=list)
