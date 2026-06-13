from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.AddressBookSerializerDict import AddressBookSerializerDict
from app.module.contact.serializer.AddressBooksSerializer import AddressBooksSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook


class AddressBooksSerializerList(AddressBooksSerializer[list]):
    """Converts a list of CardAddressBook objects to a list of dicts."""

    def __init__(self, book_serializer: AddressBookSerializerDict | None = None) -> None:
        self._book_serializer: AddressBookSerializerDict = book_serializer or AddressBookSerializerDict()

    def serialize(self, data: list[CardAddressBook]) -> list[dict[str, Any]]:
        return [self._book_serializer.serialize(book) for book in data]
