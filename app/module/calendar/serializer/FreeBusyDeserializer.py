from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.module.calendar.model.CalFreeBusyRequest import CalFreeBusyRequest
from app.module.calendar.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalFreeBusyPeriod import CalFreeBusyPeriod

T = TypeVar("T")


class FreeBusyDeserializer(Deserializer[T, CalFreeBusyRequest], Generic[T]):
    """Abstract base class for free/busy deserializers."""
