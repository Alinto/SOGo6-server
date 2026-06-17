from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.model.AddressBookContent import AddressBookContent
from app.module.contact.serializer.CardContactDeserializerLdif import CardContactDeserializerLdif
from app.module.contact.serializer.CardListDeserializerLdif import CardListDeserializerLdif
from app.utils.serializer.Deserializer import Deserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class AddressBookContentDeserializerLdif(Deserializer[str, AddressBookContent]):
    """Parse an LDIF document into a book's content: its inetOrgPerson contacts and its groupOfNames lists.

    Each record is routed to the contact or the list builder. A list references its members by DN
    (LDIF has no member UID), so members are linked best-effort to the document's contacts by matching
    the DN's cn against each contact's common name (the same name the export writes); an unmatched
    member is dropped. The persist step then reads each linked member's key.
    """

    def deserialize(self, data: str) -> AddressBookContent:
        contacts: list[CardContact] = []
        lists: list[CardList] = []
        for pairs in FormatEngineLdif.parse_records(data):
            if CardContactDeserializerLdif.is_group(pairs):
                lists.append(CardListDeserializerLdif.list_from_pairs(pairs))
            else:
                contacts.append(CardContactDeserializerLdif.contact_from_pairs(pairs))
        self._link_members(contacts, lists)
        return AddressBookContent(contacts=contacts, lists=lists)

    @classmethod
    def _link_members(cls, contacts: list[CardContact], lists: list[CardList]) -> None:
        """Link each list to the document's contacts it references, matching member DN cn to contact cn."""
        by_cn: dict[str, CardContact] = {}
        for contact in contacts:
            by_cn.setdefault(cls._contact_cn(contact), contact)
        for card_list in lists:
            card_list.member_contacts = [
                by_cn[cn] for member in card_list.members if (cn := cls._dn_cn(member)) in by_cn]

    @staticmethod
    def _contact_cn(contact: CardContact) -> str:
        """The common name the LDIF export uses for a contact (display name, structured name, or uid)."""
        return contact.display_name or " ".join(
            part for part in (contact.first_name, contact.last_name) if part) or contact.uid or "contact"

    @staticmethod
    def _dn_cn(dn: str) -> str:
        """Extract and unescape the cn value of a member DN's leading RDN (e.g. 'cn=John Doe,ou=...' -> 'John Doe')."""
        rdn: list[str] = []
        index: int = 0
        while index < len(dn) and dn[index] != ",":
            if dn[index] == "\\" and index + 1 < len(dn):
                rdn.append(dn[index:index + 2])
                index += 2
            else:
                rdn.append(dn[index])
                index += 1
        attr, _, value = "".join(rdn).partition("=")
        if attr.strip().lower() != ld.ATTR_CN.lower():
            return ""
        return FormatEngineLdif.unescape_dn(value.strip())
