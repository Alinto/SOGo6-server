from __future__ import annotations

from typing import Generic, TypeVar

from app.module.contact.model.CardList import CardList
from app.utils.serializer.Deserializer import Deserializer

T = TypeVar("T")


class CardListDeserializer(Deserializer[T, CardList], Generic[T]):
    """Abstract base class for distribution list deserializers."""
