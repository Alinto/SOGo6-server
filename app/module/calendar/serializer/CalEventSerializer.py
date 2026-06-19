from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

T = TypeVar("T")


class CalEventSerializer(Serializer["CalEvent", T], Generic[T]):
    """Abstract base class for calendar event serializers."""
