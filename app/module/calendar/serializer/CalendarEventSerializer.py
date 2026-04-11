from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventSerializer(ABC):
    """
    Abstract base class for calendar event serializers.
    """

    @abstractmethod
    def serialize(self, event: CalEvent) -> str:
        """Serialize a CalEvent to a string representation."""
