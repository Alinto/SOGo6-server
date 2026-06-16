from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.serializer.ContactSerializerLdif import ContactSerializerLdif
from app.module.contact.serializer.ContactsSerializer import ContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactsSerializerLdif(ContactsSerializer[str]):
    """Serialize a list of CardContact to an LDIF document (version header + blank-line records)."""

    def __init__(self, contact_serializer: ContactSerializerLdif | None = None) -> None:
        self._contact_serializer: ContactSerializerLdif = contact_serializer or ContactSerializerLdif()

    def serialize(self, data: list[CardContact]) -> str:
        if not data:
            return f"{ld.LDIF_VERSION_HEADER}\n"
        records: str = "\n\n".join(self._contact_serializer.serialize(contact) for contact in data)
        return f"{ld.LDIF_VERSION_HEADER}\n\n{records}\n"
