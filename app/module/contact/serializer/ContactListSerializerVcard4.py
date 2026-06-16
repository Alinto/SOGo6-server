from __future__ import annotations

from app.module.contact.serializer.ContactListSerializerVcard import ContactListSerializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine


class ContactListSerializerVcard4(ContactListSerializerVcard):
    """Serialize a CardList to a vCard 4.0 group card (KIND:group + MEMBER, RFC 6350)."""

    def version(self) -> str:
        return vc.VCARD_VERSION_4

    def _kind_line(self) -> ContentLine:
        return ContentLine(name=vc.PROP_KIND, value=vc.KIND_GROUP)

    def _member_line(self, member_uid: str) -> ContentLine:
        return ContentLine(name=vc.PROP_MEMBER, value=vc.UID_URN_PREFIX + member_uid)
