from __future__ import annotations

from datetime import datetime
from typing import Any

from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.serializer.Deserializer import Deserializer

_JSON_TYPE_TO_FB: dict[str, FreeBusyType] = {
    FreeBusyType.BUSY.value: FreeBusyType.BUSY,
    FreeBusyType.TENTATIVE.value: FreeBusyType.TENTATIVE,
    FreeBusyType.UNAVAILABLE.value: FreeBusyType.UNAVAILABLE,
}


class FreeBusyDeserializerDict(Deserializer[dict[str, Any], dict[str, list[CalFreeBusyPeriod]]]):
    """Deserializes a FreeBusy dict (as produced by CalFreeBusyResultSerializerDict) into periods per attendee."""

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        return to_utc(datetime.strptime(value.strip(), "%Y%m%dT%H%M%SZ"))

    @staticmethod
    def _parse_period(item: dict[str, Any]) -> CalFreeBusyPeriod | None:
        fb_type = _JSON_TYPE_TO_FB.get(item.get("type", ""))
        if fb_type is None:
            return None
        return CalFreeBusyPeriod(
            date_start=FreeBusyDeserializerDict._parse_dt(item["start"]),
            date_end=FreeBusyDeserializerDict._parse_dt(item["end"]),
            fb_type=fb_type,
            title=item.get("title"),
        )

    def deserialize(self, data: dict[str, Any]) -> dict[str, list[CalFreeBusyPeriod]]:
        """Parse a serialized FreeBusy dict back into a dict of periods keyed by attendee UID."""
        result: dict[str, list[CalFreeBusyPeriod]] = {}
        for uid, attendee_data in data.get("attendees", {}).items():
            periods = []
            for item in attendee_data.get("periods", []):
                period = self._parse_period(item)
                if period is not None:
                    periods.append(period)
            result[uid] = periods
        return result
