from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList

T = TypeVar("T")


class CardListSerializer(Serializer["CardList", T], Generic[T]):
    """Abstract base class for distribution list serializers."""
