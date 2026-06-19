from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.serializer.CardContactDeserializerLdif import CardContactDeserializerLdif
from app.module.contact.serializer.CardContactsDeserializer import CardContactsDeserializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class CardContactsDeserializerLdif(CardContactsDeserializer[str]):
    """Parse an LDIF document into a list of CardContact (groupOfNames records are skipped)."""

    def deserialize(self, data: str) -> list[CardContact]:
        contacts: list[CardContact] = []
        for pairs in FormatEngineLdif.parse_records(data):
            if not CardContactDeserializerLdif.is_group(pairs):
                contacts.append(CardContactDeserializerLdif.contact_from_pairs(pairs))
        return contacts
