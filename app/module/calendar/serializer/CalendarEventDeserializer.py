from __future__ import annotations

from abc import ABC, abstractmethod

from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventDeserializer(ABC):
    """
    Abstract base class for calendar event deserializers.
    """

    @abstractmethod
    def deserialize(self, text: str) -> CalEvent:
        """Deserialize a string representation into a CalEvent."""
