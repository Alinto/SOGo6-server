from __future__ import annotations

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.LdifFormatEngine import LdifFormatEngine
from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.ContactListDeserializer import ContactListDeserializer


class ContactListDeserializerLdif(ContactListDeserializer[str]):
    """Parse the first LDIF groupOfNames record of a document into a CardList.

    name <- cn, description <- description. members holds the raw member DN references (e.g.
    "cn=John Doe,ou=contacts"), NOT contact keys: the import orchestration resolves each DN to a
    contact of the target book.
    """

    def deserialize(self, data: str) -> CardList:
        records: list[list[tuple[str, str]]] = LdifFormatEngine.parse_records(data)
        return self._list_from_pairs(records[0] if records else [])

    @staticmethod
    def _list_from_pairs(pairs: list[tuple[str, str]]) -> CardList:
        card_list: CardList = CardList(name="")
        members: list[str] = []
        for attr, value in pairs:
            name: str = attr.lower()
            if name == ld.ATTR_CN.lower():
                card_list.name = value
            elif name == ld.ATTR_DESCRIPTION.lower():
                card_list.description = value
            elif name == ld.ATTR_MEMBER.lower():
                members.append(value)
        card_list.members = members
        return card_list
