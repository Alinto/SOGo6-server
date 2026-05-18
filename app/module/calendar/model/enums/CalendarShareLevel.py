from __future__ import annotations

from enum import IntEnum


class CalendarShareLevel(IntEnum):
    """Ordered permission level for a shared calendar.

    IntEnum values define the capability hierarchy:
    NONE(0) < VIEW_DATETIME(1) < VIEW_ALL(2) < RESPOND(3) < MODIFY(4)
    Each level grants all capabilities of the levels below it,
    so comparisons like ``level >= VIEW_ALL`` work naturally.
    """

    NONE = 0
    VIEW_DATETIME = 1
    VIEW_ALL = 2
    RESPOND = 3
    MODIFY = 4
