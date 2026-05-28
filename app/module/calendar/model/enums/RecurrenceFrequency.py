from __future__ import annotations

from enum import Enum


class RecurrenceFrequency(Enum):
    """
    Frequency of a recurring calendar event (RFC 5545 RRULE FREQ).
    """
    SECONDLY = "secondly"
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
