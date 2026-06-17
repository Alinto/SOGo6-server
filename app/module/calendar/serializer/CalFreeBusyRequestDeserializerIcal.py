from __future__ import annotations

from typing import Any, cast

from icalendar import Calendar

from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.model.CalFreeBusyRequest import CalFreeBusyRequest
from app.module.calendar.serializer.CalFreeBusyRequestDeserializer import CalFreeBusyRequestDeserializer
from app.utils import errors as err
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.exceptions import RequestException

# RFC 5545 §3.2.9 — reverse mapping from iCal FBTYPE to internal enum
_FBTYPE_TO_FB: dict[str, FreeBusyType] = {
    "BUSY": FreeBusyType.BUSY,
    "BUSY-TENTATIVE": FreeBusyType.TENTATIVE,
    "BUSY-UNAVAILABLE": FreeBusyType.UNAVAILABLE,
}


class CalFreeBusyRequestDeserializerIcal(CalFreeBusyRequestDeserializer[str]):
    """Deserializes VCALENDAR/VFREEBUSY iCalendar strings.

    Two entry points:
    - deserialize(): parses a VFREEBUSY REQUEST (RFC 5546 §3.3) into a CalFreeBusyRequest
    - parse_reply(): parses a VFREEBUSY REPLY into a flat list of CalFreeBusyPeriod
    """

    @staticmethod
    def _strip_mailto(value: str) -> str:
        return value.removeprefix("mailto:")

    def deserialize(self, data: str) -> CalFreeBusyRequest:
        """Parse a VFREEBUSY METHOD:REQUEST (RFC 5546 §3.3) and return a CalFreeBusyRequest.

        Raises RequestException if the iCal body is malformed or missing required fields.
        """
        try:
            cal = Calendar.from_ical(data)
        except Exception as exc:
            raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_INVALID_REQUEST) from exc

        for component in cal.walk("VFREEBUSY"):
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")
            if dtstart is None or dtend is None:
                raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_INVALID_REQUEST)

            attendees: list[str] = []
            organizer: str | None = None

            for prop_name, prop_val in component.property_items():
                if prop_name == "ATTENDEE":
                    attendees.append(self._strip_mailto(str(prop_val)))
                elif prop_name == "ORGANIZER":
                    organizer = self._strip_mailto(str(prop_val))

            if not attendees:
                raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_INVALID_REQUEST)

            return CalFreeBusyRequest(
                start=to_utc(dtstart.dt),
                end=to_utc(dtend.dt),
                attendees=attendees,
                organizer=organizer,
            )

        raise RequestException(error=err.ERROR_CALENDAR_FREEBUSY_INVALID_REQUEST)

    def parse_reply(self, text: str) -> list[CalFreeBusyPeriod]:
        """Parse a VFREEBUSY REPLY into a flat list of CalFreeBusyPeriod."""
        cal = Calendar.from_ical(text)
        periods: list[CalFreeBusyPeriod] = []

        for component in cal.walk("VFREEBUSY"):
            for prop_name, prop_val in component.property_items():
                if prop_name != "FREEBUSY":
                    continue
                # icalendar's property_items types values as ``object``; FREEBUSY carries a vPeriod.
                prop: Any = cast(Any, prop_val)
                fbtype_str = prop.params.get("FBTYPE", "BUSY").upper()
                fb_type = _FBTYPE_TO_FB.get(fbtype_str)
                if fb_type is None:
                    continue
                start, end = prop.dt
                periods.append(CalFreeBusyPeriod(
                    date_start=to_utc(start),
                    date_end=to_utc(end),
                    fb_type=fb_type,
                ))

        return periods
