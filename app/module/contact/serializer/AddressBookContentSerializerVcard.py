from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.AddressBookContent import AddressBookContent
    from app.module.contact.serializer.CardListSerializerVcard import CardListSerializerVcard
    from app.module.contact.serializer.CardContactSerializerVcard import CardContactSerializerVcard


class AddressBookContentSerializerVcard(Serializer["AddressBookContent", str]):
    """Serialize a book's contacts and lists to a single multi-card .vcf document.

    Concatenates each contact's card then each list's group card (a .vcf is just the
    BEGIN:VCARD..END:VCARD blocks back to back); the vCard version is the injected serializers'.
    """

    def __init__(self, contact_serializer: CardContactSerializerVcard, list_serializer: CardListSerializerVcard) -> None:
        self._contact_serializer: CardContactSerializerVcard = contact_serializer
        self._list_serializer: CardListSerializerVcard = list_serializer

    def serialize(self, data: AddressBookContent) -> str:
        cards: str = "".join(self._contact_serializer.serialize(contact) for contact in data.contacts)
        groups: str = "".join(self._list_serializer.serialize(card_list) for card_list in data.lists)
        return cards + groups
