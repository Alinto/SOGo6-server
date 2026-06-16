from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact

T = TypeVar("T")


class ContactsDeserializer(Deserializer[T, "list[CardContact]"], Generic[T]):
    """Abstract base class for deserializers that produce a list of contacts."""
