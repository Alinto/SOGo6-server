from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from icalendar import FreeBusy

from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.serializer.FreeBusySerializer import FreeBusySerializer
from app.module.calendar.serializer.IcalSerializerUtils import new_vcalendar
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.maths.sogo_hash import generate_uuid

if TYPE_CHECKING:
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod

# RFC 5545 §3.2.9 — FBTYPE parameter values
_FB_TYPE_MAP: dict[FreeBusyType, str] = {
    FreeBusyType.BUSY: "BUSY",
    FreeBusyType.TENTATIVE: "BUSY-TENTATIVE",
    FreeBusyType.UNAVAILABLE: "BUSY-UNAVAILABLE",
}


class FreeBusySerializerIcal(FreeBusySerializer[str]):
    """Serializes free/busy periods to a VCALENDAR/VFREEBUSY iCalendar string (RFC 5546 §3.3).

    One VFREEBUSY component is emitted per attendee.
    An optional organizer_uid can be injected via the constructor.
    """

    def __init__(self, organizer_uid: str = "") -> None:
        self._organizer_uid: str = organizer_uid

    def serialize(self, data: CalFreeBusyResult) -> str:  # pylint: disable=too-many-locals
        cal = new_vcalendar(method="REPLY")

        start_utc = to_utc(data.start)
        end_utc = to_utc(data.end)
        now = datetime.now(timezone.utc)

        for uid, periods in data.periods_by_uid.items():
            fb = FreeBusy()
            fb.add("uid", generate_uuid())
            fb.add("dtstamp", now)
            fb.add("dtstart", start_utc)
            fb.add("dtend", end_utc)
            fb.add("attendee", f"mailto:{uid}")
            if self._organizer_uid:
                fb.add("organizer", f"mailto:{self._organizer_uid}")

            by_type: dict[FreeBusyType, list[CalFreeBusyPeriod]] = {}
            for period in periods:
                by_type.setdefault(period.fb_type, []).append(period)

            for fb_type, type_periods in by_type.items():
                fb.add(
                    "freebusy",
                    [(to_utc(p.date_start), to_utc(p.date_end)) for p in type_periods],
                    parameters={"FBTYPE": _FB_TYPE_MAP[fb_type]},
                )

            cal.add_component(fb)

        return cal.to_ical().decode("utf-8")
