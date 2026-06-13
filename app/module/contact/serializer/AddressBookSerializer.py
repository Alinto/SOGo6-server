from __future__ import annotations

from typing import Generic, TYPE_CHECKING, TypeVar

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook

T = TypeVar("T")


class AddressBookSerializer(Serializer["CardAddressBook", T], Generic[T]):
    """Abstract base class for address book serializers."""
