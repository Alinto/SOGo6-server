from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult
from app.module.calendar.model.enums.FreeBusyType import FreeBusyType
from app.module.calendar.serializer.FreeBusySerializer import FreeBusySerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod


class FreeBusySerializerDict(FreeBusySerializer[dict]):
    """Serializes free/busy periods to a dict suitable for API responses."""

    @staticmethod
    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _period_dict(p: CalFreeBusyPeriod) -> dict[str, Any]:
        d: dict[str, Any] = {
            "start": FreeBusySerializerDict._fmt(p.date_start),
            "end": FreeBusySerializerDict._fmt(p.date_end),
            "type": p.fb_type.value,
        }
        if p.title is not None:
            d["title"] = p.title
        return d

    def serialize(self, data: CalFreeBusyResult) -> dict[str, Any]:
        result: dict[str, Any] = {
            "start": self._fmt(data.start),
            "end": self._fmt(data.end),
            "attendees": {
                uid: {"periods": [self._period_dict(p) for p in periods]}
                for uid, periods in data.periods_by_uid.items()
            },
            "is_available": all(
                not any(p.fb_type in {FreeBusyType.BUSY, FreeBusyType.UNAVAILABLE} for p in periods)
                for periods in data.periods_by_uid.values()
            ),
        }
        return result
