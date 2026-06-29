from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.serializer.CardContactDeserializerVcard import CardContactDeserializerVcard
from app.module.contact.serializer.CardContactDeserializerVcard3 import CardContactDeserializerVcard3
from app.module.contact.serializer.CardContactDeserializerVcard4 import CardContactDeserializerVcard4
from app.module.contact.serializer.CardContactsDeserializer import CardContactsDeserializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class CardContactsDeserializerVcard(CardContactsDeserializer[str]):
    """Parse a multi-card .vcf document into a list of CardContact.

    Each card's VERSION is detected independently, so a file mixing 3.0 and 4.0 cards is handled.
    Distribution-list cards (KIND:group / X-ADDRESSBOOKSERVER-KIND:group) are skipped here - they are
    parsed by CardListDeserializerVcard. The reader is lenient (see CardContactDeserializerVcard).
    """

    def __init__(self) -> None:
        self._by_version: dict[str, CardContactDeserializerVcard] = {
            vc.VCARD_VERSION_3: CardContactDeserializerVcard3(),
            vc.VCARD_VERSION_4: CardContactDeserializerVcard4(),
        }

    def deserialize(self, data: str) -> list[CardContact]:
        contacts: list[CardContact] = []
        for body in FormatEngineVcard.split_items(data):
            if CardContactDeserializerVcard.is_group_card(body):
                continue
            version: str = CardContactDeserializerVcard.detect_version(body)
            contacts.append(self._by_version[version].deserialize(body))
        return contacts
