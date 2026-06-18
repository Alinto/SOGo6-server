from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.serializer.CardContactSerializerDict import CardContactSerializerDict
from app.module.contact.serializer.CardListSerializerDict import CardListSerializerDict
from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.AddressBookContent import AddressBookContent
    from app.module.contact.model.CardList import CardList


class AddressBookContentSerializerDict(Serializer["AddressBookContent", dict[str, Any]]):
    """Serialize a book's content (contacts + lists) to a portable JSON-ready dict (export/import format).

    Portable means uid-based and free of server-internal handles: the contact / list ``key`` and
    ``addressbook_key`` are dropped, and a list's members are emitted as the member contacts' uids
    (not their keys) - so a re-import resolves membership by uid, exactly like vCard / LDIF.
    """

    def __init__(self) -> None:
        self._contact_serializer: CardContactSerializerDict = CardContactSerializerDict()
        self._list_serializer: CardListSerializerDict = CardListSerializerDict()

    def serialize(self, data: AddressBookContent) -> dict[str, Any]:
        return {
            "contacts": [self._portable_contact(self._contact_serializer.serialize(contact))
                         for contact in data.contacts],
            "lists": [self._portable_list(self._list_serializer.serialize(card_list), card_list)
                      for card_list in data.lists],
        }

    @staticmethod
    def _portable_contact(item: dict[str, Any]) -> dict[str, Any]:
        """Drop the server-internal handles from a contact dict, leaving the portable uid-keyed form."""
        item.pop("key", None)
        item.pop("addressbook_key", None)
        return item

    @staticmethod
    def _portable_list(item: dict[str, Any], card_list: CardList) -> dict[str, Any]:
        """Drop the internal handles from a list dict and express membership by member uid."""
        item.pop("key", None)
        item.pop("addressbook_key", None)
        item["members"] = [member.uid for member in card_list.member_contacts if member.uid]
        return item
