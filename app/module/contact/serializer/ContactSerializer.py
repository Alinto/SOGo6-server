from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact

T = TypeVar("T")


class ContactSerializer(Serializer["CardContact", T], Generic[T]):
    """Abstract base class for contact serializers."""
