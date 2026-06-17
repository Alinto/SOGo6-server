from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactDeserializerVcard import ContactDeserializerVcard
from app.module.contact.serializer.ContactDeserializerVcard3 import ContactDeserializerVcard3
from app.module.contact.serializer.ContactDeserializerVcard4 import ContactDeserializerVcard4
from app.module.contact.serializer.ContactsDeserializer import ContactsDeserializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactsDeserializerVcard(ContactsDeserializer[str]):
    """Parse a multi-card .vcf document into a list of CardContact.

    Each card's VERSION is detected independently, so a file mixing 3.0 and 4.0 cards is handled.
    Distribution-list cards (KIND:group / X-ADDRESSBOOKSERVER-KIND:group) are skipped here - they are
    parsed by ContactListDeserializerVcard. The reader is lenient (see ContactDeserializerVcard).
    """

    def __init__(self) -> None:
        self._by_version: dict[str, ContactDeserializerVcard] = {
            vc.VCARD_VERSION_3: ContactDeserializerVcard3(),
            vc.VCARD_VERSION_4: ContactDeserializerVcard4(),
        }

    def deserialize(self, data: str) -> list[CardContact]:
        contacts: list[CardContact] = []
        for body in FormatEngineVcard.split_items(data):
            if ContactDeserializerVcard.is_group_card(body):
                continue
            version: str = ContactDeserializerVcard.detect_version(body)
            contacts.append(self._by_version[version].deserialize(body))
        return contacts
