from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.serializer.CardContactDeserializerVcard import CardContactDeserializerVcard
from app.module.contact.serializer.CardListDeserializerVcard import CardListDeserializerVcard
from app.module.contact.serializer.CardContactsDeserializerVcard import CardContactsDeserializerVcard
from app.utils.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class AddressBookContentDeserializerVcard(Deserializer[str, AddressBookContent]):
    """Parse a .vcf document into a book's content: its contacts and its distribution lists.

    Contacts are read by CardContactsDeserializerVcard (group cards skipped); the group cards are read
    here by CardListDeserializerVcard. Each list's parsed members (bare UIDs) are linked to the
    parsed contacts of the same document via member_contacts, so the import can read each member's
    key once the contacts are persisted - no format-specific resolution leaks into the module.
    """

    def __init__(self) -> None:
        self._contacts_deserializer: CardContactsDeserializerVcard = CardContactsDeserializerVcard()
        self._list_deserializer: CardListDeserializerVcard = CardListDeserializerVcard()

    def deserialize(self, data: str) -> AddressBookContent:
        contacts: list[CardContact] = self._contacts_deserializer.deserialize(data)
        lists: list[CardList] = [
            self._list_deserializer.deserialize(body)
            for body in FormatEngineVcard.split_items(data)
            if CardContactDeserializerVcard.is_group_card(body)
        ]
        self._link_members(contacts, lists)
        return AddressBookContent(contacts=contacts, lists=lists)

    @staticmethod
    def _link_members(contacts: list[CardContact], lists: list[CardList]) -> None:
        """Link each list to the document's contacts it references by UID (member_contacts).

        A member UID with no matching contact in the document is dropped (e.g. a bare mailto: kept as
        its raw reference by the list deserializer); the persist step reads each member's key.
        """
        by_uid: dict[str, CardContact] = {contact.uid: contact for contact in contacts if contact.uid}
        for card_list in lists:
            card_list.member_contacts = [by_uid[ref] for ref in card_list.members if ref in by_uid]
