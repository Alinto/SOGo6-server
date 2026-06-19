from __future__ import annotations

from enum import IntEnum


class CalendarShareLevel(IntEnum):
    """Ordered permission level for a shared calendar.

    IntEnum values define the capability hierarchy:
    NONE(0) < VIEW_DATETIME(1) < VIEW_ALL(2) < RESPOND(3) < MODIFY_IF_ORG(4) < MODIFY(5)
    Each level grants all capabilities of the levels below it,
    so comparisons like ``level >= VIEW_ALL`` work naturally.

    MODIFY_IF_ORG is conditional: it grants MODIFY only on events whose ORGANIZER is the
    acting user, and behaves as RESPOND otherwise. The event context is required, so a
    calendar-level MODIFY check never passes with this level alone.
    """

    NONE = 0
    VIEW_DATETIME = 1
    VIEW_ALL = 2
    RESPOND = 3
    MODIFY_IF_ORG = 4
    MODIFY = 5
