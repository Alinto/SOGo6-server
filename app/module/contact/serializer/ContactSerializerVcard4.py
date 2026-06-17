from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactSerializerVcard import ContactSerializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine

if TYPE_CHECKING:
    from datetime import date


class ContactSerializerVcard4(ContactSerializerVcard):
    """Serialize a CardContact to vCard 4.0 (RFC 6350)."""

    def version(self) -> str:
        return vc.VCARD_VERSION_4

    def _format_date(self, value: date) -> str:
        # 4.0 dates use the basic form YYYYMMDD; the extended form is disallowed (RFC 6350 §4.3.1).
        return value.strftime("%Y%m%d")

    def _format_uid(self, uid: str) -> str:
        # 4.0 UID is preferably a URI; prefix a bare uuid so MEMBER:urn:uuid:<uid> matches it.
        return uid if ":" in uid else vc.UID_URN_PREFIX + uid

    def _type_params(self, types: list[str], pref: int | None) -> dict[str, list[str]]:
        # 4.0: TYPE is a comma list, PREF is a dedicated parameter (1 = most preferred).
        params: dict[str, list[str]] = {}
        if types:
            params[vc.PARAM_TYPE] = list(types)
        if pref is not None:
            params[vc.PARAM_PREF] = [str(pref)]
        return params

    def _kind_lines(self, kind: str) -> list[ContentLine]:
        return [ContentLine(name=vc.PROP_KIND, value=kind)]

    def _anniversary_name(self) -> str:
        return vc.PROP_ANNIVERSARY

    def _geo_value(self, geo: str) -> str:
        # 4.0 GEO is a "geo:lat,lon" URI, which is the form already stored on the model.
        return geo

    def _photo_line(self, value: str) -> ContentLine:
        # 4.0 PHOTO is a URI value: a data: URI carries an inline image directly (RFC 6350 §6.2.4).
        return ContentLine(name=vc.PROP_PHOTO, value=value)
