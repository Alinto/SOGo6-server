from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

T = TypeVar("T")


class CalendarEventsSerializer(Serializer["list[CalEvent]", T], Generic[T]):
    """Abstract base class for serializers that convert a list of events."""
