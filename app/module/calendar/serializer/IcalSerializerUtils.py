from __future__ import annotations

from icalendar import Calendar

from app.module.calendar.serializer.IcalConst import CALSCALE, ICAL_VERSION, PRODID


def new_vcalendar(prodid: str = PRODID, calscale: str = CALSCALE, method: str | None = None) -> Calendar:
    """Create a VCALENDAR envelope with the mandatory RFC 5545 header properties.

    Shared by every iCalendar serializer so the PRODID/VERSION/CALSCALE boilerplate lives in one
    place. ``method`` adds the iTIP METHOD property (RFC 5546) for transport messages (iMIP,
    free/busy reply); leave it None for plain calendar documents.
    """
    cal: Calendar = Calendar()
    cal.add("prodid", prodid)
    cal.add("version", ICAL_VERSION)
    cal.add("calscale", calscale)
    if method:
        cal.add("method", method)
    return cal
