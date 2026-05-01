from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Union

TIn = TypeVar("TIn")  # pylint: disable=invalid-name
TOut = TypeVar("TOut")  # pylint: disable=invalid-name


class Deserializer(ABC, Generic[TIn, TOut]):
    """Base contract for all deserializers. Subclasses implement deserialize()."""

    @abstractmethod
    def deserialize(self, data: TIn) -> TOut:
        """Convert data from TIn to TOut."""

    def deserialize_with_update(self, origin: TOut, update: Union[TIn, TOut]) -> TOut:
        """Apply an update to an existing object and return the result.

        When update is TIn (e.g. a dict), parse its fields and apply them to a copy of origin.
        When update is TOut (e.g. a CalEvent), return it directly as a full replacement.
        Subclasses override to provide type-specific logic.
        """
        return update  # type: ignore[return-value]
