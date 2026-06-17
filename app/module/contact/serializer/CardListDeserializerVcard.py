from __future__ import annotations

from app.module.contact.model.CardList import CardList
from app.module.contact.serializer.CardListDeserializer import CardListDeserializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard


class CardListDeserializerVcard(CardListDeserializer[str]):
    """Parse a vCard group card (KIND:group / X-ADDRESSBOOKSERVER-KIND:group) into a CardList.

    name <- FN, description <- NOTE, uid <- UID. members holds the parsed MEMBER references as bare
    UIDs (the urn:uuid: prefix stripped), NOT yet contact keys: the import orchestration resolves
    each UID to a contact of the target book. Tolerant of both the 4.0 (MEMBER) and the 3.0 / Apple
    (X-ADDRESSBOOKSERVER-MEMBER) forms; a non-resolvable member (e.g. a bare mailto:) is kept as its
    raw reference and dropped later when it does not match a contact.
    """

    def deserialize(self, data: str) -> CardList:
        card_list: CardList = CardList(name="")
        members: list[str] = []
        for line in FormatEngineVcard.parse_item(data):
            if line.name == vc.PROP_FN:
                card_list.name = FormatEngineVcard.unescape_text(line.value)
            elif line.name == vc.PROP_NOTE:
                card_list.description = FormatEngineVcard.unescape_text(line.value)
            elif line.name == vc.PROP_UID:
                card_list.uid = self._strip_uid_prefix(line.value)
            elif line.name in (vc.PROP_MEMBER, vc.PROP_X_ABS_MEMBER):
                members.append(self._strip_uid_prefix(line.value))
        card_list.members = members
        return card_list

    @staticmethod
    def _strip_uid_prefix(value: str) -> str:
        """Drop a leading 'urn:uuid:' from a UID or MEMBER reference, leaving any other form intact."""
        text: str = value.strip()
        return text[len(vc.UID_URN_PREFIX):] if text.lower().startswith(vc.UID_URN_PREFIX) else text
