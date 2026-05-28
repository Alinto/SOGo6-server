from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar

T = TypeVar("T")


class CalendarDeserializer(Deserializer[T, "CalCalendar"], Generic[T]):
    """Abstract base class for deserializers that parse a source into a calendar collection."""
