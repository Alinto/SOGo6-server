from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar

T = TypeVar("T")


class CalendarsSerializer(Serializer["list[CalCalendar]", T], Generic[T]):
    """Abstract base class for serializers that convert a list of calendars."""
