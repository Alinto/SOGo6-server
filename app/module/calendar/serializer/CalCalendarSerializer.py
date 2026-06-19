from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar

T = TypeVar("T")


class CalCalendarSerializer(Serializer["CalCalendar", T], Generic[T]):
    """Abstract base class for calendar serializers."""
