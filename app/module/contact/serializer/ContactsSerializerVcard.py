from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactsSerializer import ContactsSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.serializer.ContactSerializerVcard import ContactSerializerVcard


class ContactsSerializerVcard(ContactsSerializer[str]):
    """Serialize a list of CardContact to a multi-card .vcf document.

    Delegates each card to a single-contact vCard serializer (whose version this list inherits): a
    .vcf file is simply the BEGIN:VCARD..END:VCARD blocks concatenated.
    """

    def __init__(self, contact_serializer: ContactSerializerVcard) -> None:
        self._contact_serializer: ContactSerializerVcard = contact_serializer

    def serialize(self, data: list[CardContact]) -> str:
        return "".join(self._contact_serializer.serialize(contact) for contact in data)
