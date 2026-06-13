from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact

T = TypeVar("T")


class ContactsSerializer(Serializer["list[CardContact]", T], Generic[T]):
    """Abstract base class for serializers that convert a list of contacts."""
