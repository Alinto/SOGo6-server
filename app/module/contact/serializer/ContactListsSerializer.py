from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList

T = TypeVar("T")


class ContactListsSerializer(Serializer["list[CardList]", T], Generic[T]):
    """Abstract base class for serializers that convert a list of distribution lists."""
