from __future__ import annotations

from typing import Generic, TypeVar

from app.module.calendar.model.CalEvent import CalEvent
from app.utils.serializer.Deserializer import Deserializer

T = TypeVar("T")


class CalendarEventDeserializer(Deserializer[T, CalEvent], Generic[T]):
    """Abstract base class for calendar event deserializers."""
