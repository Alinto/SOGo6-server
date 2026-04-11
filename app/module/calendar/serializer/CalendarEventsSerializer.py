from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventsSerializer(ABC):
    """Abstract base class for serializers that convert a list of events to a string."""

    @abstractmethod
    def serialize(self, events: list[CalEvent]) -> str:
        """Serialize a list of CalEvent objects to a string representation."""
