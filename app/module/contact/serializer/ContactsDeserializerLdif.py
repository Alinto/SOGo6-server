from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.serializer.ContactDeserializerLdif import ContactDeserializerLdif
from app.module.contact.serializer.ContactsDeserializer import ContactsDeserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactsDeserializerLdif(ContactsDeserializer[str]):
    """Parse an LDIF document into a list of CardContact (groupOfNames records are skipped)."""

    def deserialize(self, data: str) -> list[CardContact]:
        contacts: list[CardContact] = []
        for pairs in FormatEngineLdif.parse_records(data):
            if not self._is_group(pairs):
                contacts.append(ContactDeserializerLdif.contact_from_pairs(pairs))
        return contacts

    @staticmethod
    def _is_group(pairs: list[tuple[str, str]]) -> bool:
        """Whether an LDIF record is a groupOfNames (a distribution list) rather than a person."""
        return any(attr.lower() == ld.ATTR_OBJECTCLASS.lower() and value == ld.OC_GROUPOFNAMES
                   for attr, value in pairs)
