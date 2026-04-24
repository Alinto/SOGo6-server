from __future__ import annotations

from datetime import datetime
from typing import Generic, TYPE_CHECKING, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.module.calendar.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

T = TypeVar("T")


class CalendarEventSerializer(Serializer["CalEvent", T], Generic[T]):
    """Abstract base class for calendar event serializers."""

    @staticmethod
    def _apply_tz(dt: datetime, tz_name: str) -> str | None:
        """Convert dt to the given IANA timezone and return an ISO 8601 string with UTC offset.

        Returns None when tz_name is unknown or the conversion fails.
        """
        try:
            return dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except (ZoneInfoNotFoundError, KeyError):
            return None
