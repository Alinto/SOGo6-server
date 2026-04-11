from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent


class CalendarEventsDeserializer(ABC):
    """Abstract base class for deserializers that parse a string into a list of events."""

    @abstractmethod
    def deserialize(self, text: str) -> list[CalEvent]:
        """Deserialize a string representation into a list of CalEvent objects."""
