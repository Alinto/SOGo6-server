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
        """Link each list to the document's contacts it references.

        A member DN carries the uid as a second RDN component (cn=...+uid=...); members are matched
        on uid first (stable, unique) and fall back to the cn when the DN has no uid.
        """
        by_uid: dict[str, CardContact] = {contact.uid: contact for contact in contacts if contact.uid}
        by_cn: dict[str, CardContact] = {}
        for contact in contacts:
            by_cn.setdefault(cls._contact_cn(contact), contact)
        for card_list in lists:
            linked: list[CardContact] = []
            for member in card_list.members:
                rdn: dict[str, str] = cls._dn_rdn_components(member)
                uid: str = rdn.get(ld.ATTR_UID.lower(), "")
                common_name: str = rdn.get(ld.ATTR_CN.lower(), "")
                if uid and uid in by_uid:
                    linked.append(by_uid[uid])
                elif common_name and common_name in by_cn:
                    linked.append(by_cn[common_name])
            card_list.member_contacts = linked

    @staticmethod
    def _contact_cn(contact: CardContact) -> str:
        """The common name the LDIF export uses for a contact (display name, structured name, or uid)."""
        return contact.display_name or " ".join(
            part for part in (contact.first_name, contact.last_name) if part) or contact.uid or "contact"

    @staticmethod
    def _dn_rdn_components(dn: str) -> dict[str, str]:
        """Parse the leading (possibly multi-valued) RDN of a DN into {attribute_lower: unescaped_value}.

        The RDN ends at the first unescaped ',' and its components are split on unescaped '+'
        (e.g. 'cn=John Doe+uid=42,ou=...' -> {'cn': 'John Doe', 'uid': '42'}).
        """
        parts: list[str] = [""]
        index: int = 0
        while index < len(dn) and dn[index] != ",":
            if dn[index] == "\\" and index + 1 < len(dn):
                parts[-1] += dn[index:index + 2]
                index += 2
                continue
            if dn[index] == "+":
                parts.append("")
            else:
                parts[-1] += dn[index]
            index += 1
        components: dict[str, str] = {}
        for part in parts:
            attr, sep, value = part.partition("=")
            if sep:
                components[attr.strip().lower()] = FormatEngineLdif.unescape_dn(value.strip())
        return components
