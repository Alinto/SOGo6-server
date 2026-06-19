from __future__ import annotations

from typing import Generic, TypeVar

from app.module.contact.model.CardContact import CardContact
from app.utils.serializer.Deserializer import Deserializer

T = TypeVar("T")


class CardContactDeserializer(Deserializer[T, CardContact], Generic[T]):
    """Abstract base class for contact deserializers."""
