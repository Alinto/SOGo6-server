from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.serializer.ContactSerializerVcard import ContactSerializerVcard
from app.module.contact.format.vcard import VcardConst as vc
from app.module.contact.format.ContentLine import ContentLine

if TYPE_CHECKING:
    from datetime import date


class ContactSerializerVcard3(ContactSerializerVcard):
    """Serialize a CardContact to vCard 3.0 (RFC 2426)."""

    def version(self) -> str:
        return vc.VCARD_VERSION_3

    def _format_date(self, value: date) -> str:
        # 3.0 dates use the ISO extended form YYYY-MM-DD (RFC 2426).
        return value.isoformat()

    def _format_uid(self, uid: str) -> str:
        # 3.0 keeps the UID value as-is (Apple's X-ADDRESSBOOKSERVER convention uses the bare uid).
        return uid

    def _type_params(self, types: list[str], pref: int | None) -> dict[str, list[str]]:
        # 3.0 has no PREF parameter: the preferred entry is marked with the TYPE value "pref".
        values: list[str] = list(types)
        if pref is not None:
            values.append(vc.PARAM_VALUE_PREF)
        return {vc.PARAM_TYPE: values} if values else {}

    def _kind_lines(self, kind: str) -> list[ContentLine]:
        # 3.0 has no KIND property for individual contacts (groups use X-ADDRESSBOOKSERVER-KIND,
        # handled by the distribution-list serializer, not here).
        return []

    def _anniversary_name(self) -> str:
        return vc.PROP_X_ANNIVERSARY

    def _geo_value(self, geo: str) -> str:
        # 3.0 GEO is "lat;lon"; drop the 4.0 "geo:" URI prefix and swap the separator.
        coordinates: str = geo[len(vc.GEO_URI_PREFIX):] if geo.startswith(vc.GEO_URI_PREFIX) else geo
        return coordinates.replace(",", ";")
