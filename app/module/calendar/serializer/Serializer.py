from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TIn = TypeVar("TIn")  # pylint: disable=invalid-name
TOut = TypeVar("TOut")  # pylint: disable=invalid-name


class Serializer(ABC, Generic[TIn, TOut]):
    """Base contract for all serializers. Subclasses implement serialize()."""

    @abstractmethod
    def serialize(self, data: TIn) -> TOut:
        """Convert data from TIn to TOut."""
