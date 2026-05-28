from __future__ import annotations

from app.module.calendar.source.CalendarSourceDb import CalendarSourceDb


class CalendarSourceIcsMirror(CalendarSourceDb):
    """DB-backed source for external ICS calendars.

    Events are populated by the sync engine. Write restrictions are enforced
    by CalendarAclEngine at the module level, not by the source itself.
    This subclass exists for future ICS-specific behavior (e.g. sync metadata,
    custom fetch pipeline).
    """
