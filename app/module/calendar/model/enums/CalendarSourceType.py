from __future__ import annotations

from enum import Enum


class CalendarSourceType(Enum):
    """Discriminates calendar backend origin."""

    UNDEFINED = "undefined"
    LOCAL = "local"
    ICS = "ics"
    CALDAV = "caldav"
