from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.model.enums.ContactImportFormat import ContactImportFormat
from app.module.contact.serializer.CardContactDeserializerDict import CardContactDeserializerDict
from app.module.contact.serializer.CardListDeserializerDict import CardListDeserializerDict
from app.utils.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class AddressBookContentDeserializerDict(Deserializer[dict[str, Any], AddressBookContent]):
    """Parse a portable JSON book document ({"contacts": [...], "lists": [...]}) into an AddressBookContent.

    The document is uid-keyed (no server handles): a list's members are member uids. Members are linked
    to the parsed contacts (by uid) via member_contacts so the import can read each member's key once
    persisted - the same contract as the vCard / LDIF document deserializers, no format-specific logic
    in the module. Contacts parsed from a JSON document have UNDEFINED provenance: import_format is
    server-set, never trusted from the payload.
    """

    def __init__(self) -> None:
        self._contact_deserializer: CardContactDeserializerDict = CardContactDeserializerDict()
        self._list_deserializer: CardListDeserializerDict = CardListDeserializerDict()

    def deserialize(self, data: dict[str, Any]) -> AddressBookContent:
        contacts: list[CardContact] = [
            self._contact_deserializer.deserialize(item) for item in data.get("contacts", [])]
        for contact in contacts:
            contact.import_format = ContactImportFormat.UNDEFINED
        by_uid: dict[str, CardContact] = {contact.uid: contact for contact in contacts if contact.uid}
        lists: list[CardList] = []
        for item in data.get("lists", []):
            card_list: CardList = self._list_deserializer.deserialize(item)
            card_list.member_contacts = [by_uid[uid] for uid in item.get("members", []) if uid in by_uid]
            lists.append(card_list)
        return AddressBookContent(contacts=contacts, lists=lists)
