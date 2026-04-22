from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventSerializer(ABC):
    """
    Abstract base class for calendar event serializers.
    """

    @abstractmethod
    def serialize(self, event: CalEvent) -> str:
        """Serialize a CalEvent to a string representation."""

    @staticmethod
    def _apply_tz(dt: datetime, tz_name: str) -> str | None:
        """Convert dt to the given IANA timezone and return an ISO 8601 string with UTC offset.

        Returns None when tz_name is unknown or the conversion fails.
        """
        try:
            return dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except (ZoneInfoNotFoundError, KeyError):
            return None
