from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif
from app.module.contact.serializer.CardListSerializer import CardListSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact
    from app.module.contact.model.CardList import CardList


class CardListSerializerLdif(CardListSerializer[str]):
    """Serialize a CardList to an LDIF groupOfNames record; members are the contacts' entry DNs."""

    def serialize(self, data: CardList) -> str:
        lines: list[str] = [FormatEngineLdif.emit_attr(ld.ATTR_DN, self._dn(data.name))]
        for object_class in (ld.OC_TOP, ld.OC_GROUPOFNAMES):
            lines.append(FormatEngineLdif.emit_attr(ld.ATTR_OBJECTCLASS, object_class))
        lines.append(FormatEngineLdif.emit_attr(ld.ATTR_CN, data.name))
        if data.description:
            lines.append(FormatEngineLdif.emit_attr(ld.ATTR_DESCRIPTION, data.description))
        for member in data.member_contacts:
            lines.append(FormatEngineLdif.emit_attr(ld.ATTR_MEMBER, self._dn(self._member_cn(member))))
        return "\n".join(lines)

    @staticmethod
    def _member_cn(member: CardContact) -> str:
        """The common name used in a member's DN (display name, structured name, or uid)."""
        return member.display_name or " ".join(
            part for part in (member.first_name, member.last_name) if part) or member.uid or "contact"

    @staticmethod
    def _dn(common_name: str) -> str:
        """Build a distinguished name from a common name (escaped per RFC 4514)."""
        return f"{ld.ATTR_CN}={FormatEngineLdif.escape_dn(common_name)},{ld.BASE_DN}"
