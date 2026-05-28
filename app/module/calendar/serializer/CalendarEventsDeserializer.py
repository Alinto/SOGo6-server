from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

T = TypeVar("T")


class CalendarEventsDeserializer(Deserializer[T, "list[CalEvent]"], Generic[T]):
    """Abstract base class for deserializers that parse a string into a list of events."""
