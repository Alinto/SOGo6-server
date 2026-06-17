from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.serializer.CardListSerializerLdif import CardListSerializerLdif
from app.module.contact.serializer.CardContactSerializerLdif import CardContactSerializerLdif
from app.utils.serializer.Serializer import Serializer

if TYPE_CHECKING:
    from app.module.contact.model.AddressBookContent import AddressBookContent


class AddressBookContentSerializerLdif(Serializer["AddressBookContent", str]):
    """Serialize a book's contacts and lists to a single LDIF document.

    One version header for the whole document (RFC 2849), then the inetOrgPerson records and the
    groupOfNames records, blank-line separated.
    """

    def __init__(self, contact_serializer: CardContactSerializerLdif | None = None,
                 list_serializer: CardListSerializerLdif | None = None) -> None:
        self._contact_serializer: CardContactSerializerLdif = contact_serializer or CardContactSerializerLdif()
        self._list_serializer: CardListSerializerLdif = list_serializer or CardListSerializerLdif()

    def serialize(self, data: AddressBookContent) -> str:
        records: list[str] = [self._contact_serializer.serialize(contact) for contact in data.contacts]
        records += [self._list_serializer.serialize(card_list) for card_list in data.lists]
        if not records:
            return f"{ld.LDIF_VERSION_HEADER}\n"
        return f"{ld.LDIF_VERSION_HEADER}\n\n" + "\n\n".join(records) + "\n"
