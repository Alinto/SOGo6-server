from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactListSerializer import ContactListSerializer
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard

if TYPE_CHECKING:
    from app.module.contact.model.CardList import CardList


class ContactListSerializerVcard(ContactListSerializer[str], ABC):
    """Abstract base converting a CardList to a vCard group card (KIND:group, RFC 6350 §6.1.4).

    A list is a vCard whose members are MEMBER references to the member contacts' UIDs. The members
    come from CardList.member_contacts (the resolved contacts), so the export path must populate
    them; a member without a uid is skipped. The 3.0 vs 4.0 delta (KIND vs X-ADDRESSBOOKSERVER-KIND,
    MEMBER vs X-ADDRESSBOOKSERVER-MEMBER) is delegated to the concrete subclasses.
    """

    def serialize(self, data: CardList) -> str:
        """Render a CardList to a complete BEGIN:VCARD ... END:VCARD group card (CRLF-terminated)."""
        lines: list[ContentLine] = [
            ContentLine(name=vc.PROP_BEGIN, value=vc.VALUE_VCARD),
            ContentLine(name=vc.PROP_VERSION, value=self.version()),
            self._kind_line(),
            ContentLine(name=vc.PROP_FN, value=FormatEngineVcard.escape_text(data.name)),
        ]
        if data.uid:
            lines.append(ContentLine(name=vc.PROP_UID, value=data.uid))
        if data.description:
            lines.append(ContentLine(name=vc.PROP_NOTE, value=FormatEngineVcard.escape_text(data.description)))
        for member in data.member_contacts:
            if member.uid:
                lines.append(self._member_line(member.uid))
        lines.append(ContentLine(name=vc.PROP_END, value=vc.VALUE_VCARD))
        return "\r\n".join(FormatEngineVcard.emit_line(line) for line in lines) + "\r\n"

    @abstractmethod
    def version(self) -> str:
        """The VERSION value emitted ('3.0' or '4.0')."""

    @abstractmethod
    def _kind_line(self) -> ContentLine:
        """The property marking the card as a group (KIND or X-ADDRESSBOOKSERVER-KIND)."""

    @abstractmethod
    def _member_line(self, member_uid: str) -> ContentLine:
        """A member reference line for the given contact UID (MEMBER or X-ADDRESSBOOKSERVER-MEMBER)."""
