from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency


@dataclass
class CalRecurrenceRule:  # pylint: disable=too-many-instance-attributes
    """Recurrence rule for a repeating calendar event (RFC 5545 §3.8.5.3 RRULE)."""
    # RFC 5545 §3.3.10 FREQ — base recurrence frequency (DAILY, WEEKLY…)
    frequency: RecurrenceFrequency
    # RFC 5545 §3.3.10 INTERVAL — multiplier for FREQ (e.g. INTERVAL=2 WEEKLY = every 2 weeks)
    interval: int = 1
    # RFC 5545 §3.3.10 UNTIL — UTC datetime at which the recurrence ends (inclusive)
    until: datetime | None = None
    # RFC 5545 §3.3.10 COUNT — maximum number of occurrences; mutually exclusive with UNTIL
    count: int | None = None
    # RFC 5545 §3.3.10 BYDAY — day-of-week list, e.g. ["MO", "WE"] or ["1MO"] (first Monday)
    by_day: list[str] | None = None
    # RFC 5545 §3.3.10 BYMONTHDAY — day-of-month list, e.g. [1, 15] or [-1] (last day)
    by_month_day: list[int] | None = None
    # RFC 5545 §3.3.10 BYMONTH — month list (1–12)
    by_month: list[int] | None = None
    # RFC 5545 §3.3.10 BYYEARDAY — day-of-year list, e.g. [1, 365] or [-1]
    by_year_day: list[int] | None = None
    # RFC 5545 §3.3.10 BYWEEKNO — ISO week-number list (1–53 or negative)
    by_week_no: list[int] | None = None
    # RFC 5545 §3.3.10 BYSETPOS — selects the nth occurrence within the computed set
    by_set_pos: list[int] | None = None
    # RFC 5545 §3.3.10 BYHOUR — hour list (0–23)
    by_hour: list[int] | None = None
    # RFC 5545 §3.3.10 BYMINUTE — minute list (0–59)
    by_minute: list[int] | None = None
    # RFC 5545 §3.3.10 BYSECOND — second list (0–60)
    by_second: list[int] | None = None
    # RFC 5545 §3.3.10 WKST — week start day (default MO per RFC)
    week_start: str = "MO"
    # RFC 5545 §3.8.5.2 RDATE — additional explicit occurrence datetimes outside the rule
    additional_dates: list[datetime] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation of this rule.

        Only non-None / non-empty optional fields are included.
        Datetimes are formatted as ISO 8601 UTC strings (e.g. 2026-12-31T00:00:00+00:00).
        The frequency enum is stored as its lowercase string value.
        """
        d: dict[str, Any] = {"frequency": self.frequency.value, "interval": self.interval}
        if self.until is not None:
            d["until"] = self.until.isoformat()
        if self.count is not None:
            d["count"] = self.count
        if self.by_day:
            d["by_day"] = self.by_day
        if self.by_month_day:
            d["by_month_day"] = self.by_month_day
        if self.by_month:
            d["by_month"] = self.by_month
        if self.by_year_day:
            d["by_year_day"] = self.by_year_day
        if self.by_week_no:
            d["by_week_no"] = self.by_week_no
        if self.by_set_pos:
            d["by_set_pos"] = self.by_set_pos
        if self.by_hour:
            d["by_hour"] = self.by_hour
        if self.by_minute:
            d["by_minute"] = self.by_minute
        if self.by_second:
            d["by_second"] = self.by_second
        if self.week_start != "MO":
            d["week_start"] = self.week_start
        return d
