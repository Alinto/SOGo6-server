from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardAddressBookSerializerDict import CardAddressBookSerializerDict
from app.module.contact.serializer.CardAddressBooksSerializer import CardAddressBooksSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardAddressBook import CardAddressBook


class CardAddressBooksSerializerList(CardAddressBooksSerializer[list]):
    """Converts a list of CardAddressBook objects to a list of dicts."""

    def __init__(self, book_serializer: CardAddressBookSerializerDict | None = None) -> None:
        self._book_serializer: CardAddressBookSerializerDict = book_serializer or CardAddressBookSerializerDict()

    def serialize(self, data: list[CardAddressBook]) -> list[dict[str, Any]]:
        return [self._book_serializer.serialize(book) for book in data]
