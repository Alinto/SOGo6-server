from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.format.ldif import LdifConst as ld
from app.module.contact.format.ldif.LdifFormatEngine import LdifFormatEngine
from app.module.contact.serializer.ContactSerializer import ContactSerializer

if TYPE_CHECKING:
    from app.module.contact.model.CardContact import CardContact


class ContactSerializerLdif(ContactSerializer[str]):
    """Serialize a CardContact to an LDIF record (RFC 2849), mapped onto inetOrgPerson attributes."""

    def serialize(self, data: CardContact) -> str:
        common_name: str = data.display_name or self._fallback_cn(data)
        lines: list[str] = [LdifFormatEngine.emit_attr(ld.ATTR_DN, self._dn(common_name))]
        for object_class in (ld.OC_TOP, ld.OC_PERSON, ld.OC_ORGANIZATIONAL_PERSON, ld.OC_INETORGPERSON):
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_OBJECTCLASS, object_class))
        lines.append(LdifFormatEngine.emit_attr(ld.ATTR_CN, common_name))
        lines.append(LdifFormatEngine.emit_attr(ld.ATTR_SN, data.last_name or common_name))  # sn is mandatory
        if data.first_name:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_GIVENNAME, data.first_name))
        if data.display_name:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_DISPLAYNAME, data.display_name))
        for email in data.emails:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_MAIL, email.value))
        for phone in data.phones:
            attr: str = ld.ATTR_MOBILE if ld.MOBILE_TYPE in phone.types else ld.ATTR_TELEPHONE
            lines.append(LdifFormatEngine.emit_attr(attr, phone.number))
        if data.organization:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_O, data.organization))
        if data.department:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_OU, data.department))
        if data.job_title:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_TITLE, data.job_title))
        if data.note:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_DESCRIPTION, data.note))
        lines.extend(self._address_lines(data))
        if data.uid:
            lines.append(LdifFormatEngine.emit_attr(ld.ATTR_UID, data.uid))
        return "\n".join(lines)

    @staticmethod
    def _address_lines(data: CardContact) -> list[str]:
        """Emit the first postal address as the standard directory location attributes."""
        if not data.addresses:
            return []
        address = data.addresses[0]
        pairs: list[tuple[str, str | None]] = [
            (ld.ATTR_STREET, address.street), (ld.ATTR_L, address.locality), (ld.ATTR_ST, address.region),
            (ld.ATTR_POSTALCODE, address.postal_code), (ld.ATTR_C, address.country)]
        return [LdifFormatEngine.emit_attr(attr, value) for attr, value in pairs if value]

    @staticmethod
    def _dn(common_name: str) -> str:
        """Build the entry distinguished name from the common name (commas escaped per RFC 4514)."""
        escaped: str = common_name.replace("\\", "\\\\").replace(",", "\\,")
        return f"{ld.ATTR_CN}={escaped},{ld.BASE_DN}"

    @staticmethod
    def _fallback_cn(data: CardContact) -> str:
        """A common name for a contact with no display name: the structured name, or the uid."""
        return " ".join(part for part in (data.first_name, data.last_name) if part) or data.uid or "contact"
