from __future__ import annotations

from icalendar import Calendar, Component

from app.module.calendar.serializer.IcalConst import CALSCALE, ICAL_VERSION, PRODID


class EnvelopeIcal:
    """VCALENDAR envelope helpers, keeping the icalendar lib confined to a *Ical file.

    Builds the RFC 5545 header shared by every serializer and reads the iTIP METHOD from a payload,
    so no other module hand-parses raw iCalendar text.
    """

    @staticmethod
    def new_vcalendar(prodid: str = PRODID, calscale: str = CALSCALE, method: str | None = None) -> Calendar:
        """Create a VCALENDAR envelope with the mandatory RFC 5545 header properties.

        ``method`` adds the iTIP METHOD property (RFC 5546) for transport messages (iMIP, free/busy
        reply); leave it None for plain calendar documents.
        """
        cal: Calendar = Calendar()
        cal.add("prodid", prodid)
        cal.add("version", ICAL_VERSION)
        cal.add("calscale", calscale)
        if method:
            cal.add("method", method)
        return cal

    @staticmethod
    def read_method(text: str) -> str | None:
        """Return the iTIP METHOD property (uppercased) of a VCALENDAR string, or None when absent.

        Non-raising on malformed input: used as a cheap probe to recognise an iMIP attachment before
        committing to full processing.
        """
        try:
            cal: Component = Calendar.from_ical(text)
        except Exception:  # pylint: disable=broad-exception-caught
            return None
        method = cal.get("method")
        return str(method).upper() if method else None
