from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.ContactListSerializerDict import ContactListSerializerDict
from app.module.contact.serializer.ContactListsSerializer import ContactListsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList


class ContactListsSerializerList(ContactListsSerializer[list]):
    """Converts a list of CardList objects to a list of dicts."""

    def __init__(self, list_serializer: ContactListSerializerDict | None = None) -> None:
        self._list_serializer: ContactListSerializerDict = list_serializer or ContactListSerializerDict()

    def serialize(self, data: list[CardList]) -> list[dict[str, Any]]:
        return [self._list_serializer.serialize(card_list) for card_list in data]
