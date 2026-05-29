from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalFreeBusyResult import CalFreeBusyResult

T = TypeVar("T")


class FreeBusySerializer(Serializer["CalFreeBusyResult", T], Generic[T]):
    """Abstract base class for free/busy serializers."""
