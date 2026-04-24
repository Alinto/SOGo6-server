from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TIn = TypeVar("TIn")  # pylint: disable=invalid-name
TOut = TypeVar("TOut")  # pylint: disable=invalid-name


class Deserializer(ABC, Generic[TIn, TOut]):
    """Base contract for all deserializers. Subclasses implement deserialize()."""

    @abstractmethod
    def deserialize(self, data: TIn) -> TOut:
        """Convert data from TIn to TOut."""
